"""Background polling worker for browser_submission WorkflowTasks.

Mirrors backend/worker.py's poll_loop pattern: claims pending WorkflowTask
rows for workflow_type="browser_submission" and drives them through
BrowserWorker's state machine (see browser_worker/state.py and
docs/browser-state-machine-design.md), translating results into the
WorkflowStatus/task_metadata state machine that
backend/app/api/routes/browser_automation.py already reads and writes.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import (
    Application,
    ApplicationPipelineStatus,
    BrowserCheckpoint,
    BrowserPauseReason,
    BrowserSession,
    BrowserSessionStatus,
    CanonicalJob,
    CoverLetter,
    Profile,
    ResumeVersion,
    WorkflowStatus,
    WorkflowTask,
)

from .models import ApplicationData
from .worker import BrowserWorker
from .worker import _HARD_TIMEOUT_SECONDS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_POLL_INTERVAL_SECONDS = 5
_WORKFLOW_TYPE = "browser_submission"
_STORAGE_ROOT = "/app/storage"
# Must stay comfortably above worker.py's own _HARD_TIMEOUT_SECONDS - a
# legitimately still-running task (which can take up to that long before
# self-terminating) must never get reclaimed as "stuck" while it's still
# actually executing; that would let a second poll pick up the same
# session concurrently. Derived from the real constant instead of a
# separate hardcoded number specifically so the two can't drift out of
# sync again the way they briefly did here (a real long-form application -
# Epic's real Avature-hosted careers portal - needed MAX_WALL_CLOCK_SECONDS
# raised well past what this threshold had assumed).
_STALE_RUNNING_THRESHOLD_SECONDS = _HARD_TIMEOUT_SECONDS + 300


def _get_or_create_browser_session(db: Session, application: Application, task: WorkflowTask, session_key: str) -> BrowserSession:
    """session_key is deterministic per application (f"app_{application.id}"),
    which is what makes pause/resume find the same row across repeated
    pickups of the *same* WorkflowTask - required for CheckpointManager's
    durable lookups (scoped by browser_session_id) to keep working.

    But that same determinism means a resubmission (a fresh WorkflowTask for
    an application whose previous attempt already reached a terminal state)
    would otherwise silently reuse the *old* task's session row untouched -
    still pointing at the old workflow_task_id, still carrying whatever
    status a failed/completed prior attempt left behind. Since checkpoint
    lookups are scoped by browser_session_id, not by task, a resume() on the
    new task would then resume from the *previous* attempt's stale
    checkpoint instead of starting fresh. Only reset when the task actually
    changed - same-task reuse (the normal pause/resume path) must return the
    row untouched.
    """
    session = db.query(BrowserSession).filter(BrowserSession.session_key == session_key).first()
    if session is not None:
        if session.workflow_task_id != task.id:
            # session_key is unique per application (not per task), so a
            # resubmission can't get a fresh row via a schema-level identity
            # change - this row has to be reused. Resetting workflow_task_id/
            # status alone would NOT be enough on its own: CheckpointManager's
            # durable lookup is scoped by browser_session.id, which doesn't
            # change here, so the previous (now-irrelevant) attempt's
            # checkpoint rows would still be the ones resume() finds via
            # ORDER BY created_at DESC. Deleting them is what actually makes
            # this a clean start rather than a cosmetic status reset.
            stale_checkpoint_count = (
                db.query(BrowserCheckpoint).filter(BrowserCheckpoint.session_id == session.id).delete()
            )
            logger.info(
                "Resetting browser_session %s for a new workflow_task (%s -> %s) - "
                "purged %d stale checkpoint(s) from the previous attempt",
                session.id, session.workflow_task_id, task.id, stale_checkpoint_count,
            )
            session.workflow_task_id = task.id
            session.status = BrowserSessionStatus.active
            session.browser_state = "queued"
            session.pause_reason = None
            # A resubmission is a deliberate "start over" - stale cookies
            # from the previous (irrelevant) attempt could resume() into a
            # confusing half-completed state on the real site instead of a
            # genuinely clean run.
            session.storage_state = None
            db.commit()
            db.refresh(session)
        return session

    session = BrowserSession(
        application_id=application.id,
        workflow_task_id=task.id,
        session_key=session_key,
        browser_state="queued",
        status=BrowserSessionStatus.active,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _reclaim_stale_tasks(db: Session) -> None:
    """Reset WorkflowTasks stuck in `running` past the stale threshold back to `pending`.

    Handles a browser-worker crash or redeploy mid-task, which previously
    orphaned the task forever since poll_loop only ever queries for
    status="pending". A reclaimed task's next pickup goes through _run_task's
    dispatch exactly like any other pickup, which always calls
    BrowserWorker.resume() - that checks the actual last checkpoint in Postgres
    (not a lagging status field) and resumes from it correctly, closing the
    gap noted in docs/browser-state-machine-design.md section 7 (Phase 1 could
    only reset WorkflowTask.status; proper checkpoint-aware resume needed the
    state machine built in Phase 3).
    """
    stale_before = datetime.utcnow() - timedelta(seconds=_STALE_RUNNING_THRESHOLD_SECONDS)
    stale_tasks = (
        db.query(WorkflowTask)
        .filter(
            WorkflowTask.workflow_type == _WORKFLOW_TYPE,
            WorkflowTask.status == WorkflowStatus.running,
            WorkflowTask.updated_at < stale_before,
        )
        .all()
    )
    for task in stale_tasks:
        logger.warning("Reclaiming stale browser_submission task %s (stuck running since %s)", task.id, task.updated_at)
        task.status = WorkflowStatus.pending
        task.retry_count = (task.retry_count or 0) + 1
    if stale_tasks:
        db.commit()


def _build_application_data(application: Application, db: Session) -> ApplicationData:
    profile = db.query(Profile).filter(Profile.user_id == application.user_id).first()
    if profile is None or not profile.legal_name:
        raise ValueError(f"User {application.user_id} has no profile with a legal name set")
    if not profile.email:
        raise ValueError(f"Profile {profile.id} has no email set")
    if not profile.work_authorization:
        raise ValueError(f"Profile {profile.id} has no work_authorization set")

    name_parts = profile.legal_name.split(None, 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    resume_path = ""
    if application.resume_version_id:
        resume_version = (
            db.query(ResumeVersion).filter(ResumeVersion.id == application.resume_version_id).first()
        )
        if resume_version and resume_version.file_path:
            resume_path = os.path.join(_STORAGE_ROOT, resume_version.file_path)

    # Only an already-approved cover letter is truthful, reviewed content -
    # a needs_review draft must not be submitted on the user's behalf.
    cover_letter = (
        db.query(CoverLetter)
        .filter(CoverLetter.application_id == application.id, CoverLetter.status == "approved")
        .order_by(CoverLetter.updated_at.desc())
        .first()
    )

    return ApplicationData(
        application_id=str(application.id),
        first_name=first_name,
        last_name=last_name,
        email=profile.email,
        phone=profile.phone,
        linkedin=profile.linkedin,
        work_authorization=profile.work_authorization,
        resume_path=resume_path,
        interest=cover_letter.content if cover_letter else None,
        address_line1=profile.address_line1,
        city=profile.city,
        state=profile.state,
        zip_code=profile.postal_code,
        country=profile.country,
    )


def _application_url(job: CanonicalJob) -> str:
    url = (job.extracted_data or {}).get("url")
    if not url:
        raise ValueError(f"Job {job.id} has no application URL in extracted_data")
    return url


_PAUSE_REASON_MAP = {
    "captcha": BrowserPauseReason.captcha,
    "mfa": BrowserPauseReason.mfa,
    "email_verification": BrowserPauseReason.email_verification,
    "unsupported_flow": BrowserPauseReason.unsupported_flow,
    "repeated_failure": BrowserPauseReason.repeated_failure,
    "user_review": BrowserPauseReason.user_review,
}


async def _run_task(task: WorkflowTask, db: Session) -> None:
    application = db.query(Application).filter(Application.id == task.entity_id).first()
    if application is None:
        raise ValueError(f"Application {task.entity_id} not found")

    job = db.query(CanonicalJob).filter(CanonicalJob.id == application.job_id).first()
    if job is None:
        raise ValueError(f"Job {application.job_id} not found")

    application_data = _build_application_data(application, db)
    application_url = _application_url(job)
    session_id = f"app_{application.id}"
    browser_session = _get_or_create_browser_session(db, application, task, session_id)
    headless = os.environ.get("HEADLESS", "true").strip().lower() != "false"
    worker = BrowserWorker(headless=headless, db=db, browser_session_id=browser_session.id)

    ctx = worker.make_context(
        session_id=session_id,
        application_url=application_url,
        application_data=application_data,
        user_id=str(application.user_id),
        ats_platform="generic",
        tenant_key=urlparse(application_url).netloc or "default",
    )

    metadata = dict(task.task_metadata or {})

    # If the last pickup paused on a question and the user has since answered
    # it, thread that answer through so the resumed fill pass can use it
    # directly for the one field that raised it, instead of asking again.
    if metadata.get("step") == "question_answered" and metadata.get("last_answer"):
        ctx.answered_question = metadata["last_answer"]

    # Always resume: BrowserWorker.resume() checks the actual last checkpoint
    # in Postgres and falls straight through to a fresh run when none exists,
    # so this one call correctly covers first-run, post-approval, reclaimed,
    # manual-intervention-resumed, and question-answered pickups without
    # needing to distinguish most of them here.
    result = await worker.resume(ctx, approved_for_submit=(metadata.get("step") == "approved_for_submit"))

    # Drop this run's stale outcome-specific keys before re-populating below,
    # so e.g. a prior pause's "detail"/"pause_reason" doesn't linger in
    # task_metadata once the run reaches a completely different outcome.
    for stale_key in ("detail", "pause_reason", "pending_question", "last_answer"):
        metadata.pop(stale_key, None)

    metadata["updated_at"] = datetime.utcnow().isoformat()

    if not result.get("success"):
        task.status = WorkflowStatus.failed
        task.error = result.get("error", "Unknown browser automation error")
        task.retry_count = (task.retry_count or 0) + 1
        application.pipeline_status = ApplicationPipelineStatus.failed_retryable
        metadata["step"] = "failed"
        task.task_metadata = metadata
        browser_session.status = BrowserSessionStatus.failed
        browser_session.browser_state = "failed"
        return

    status = result.get("status")

    if status == "manual_intervention":
        task.status = WorkflowStatus.waiting_user_input
        task.current_step = "manual_intervention"
        application.pipeline_status = ApplicationPipelineStatus.paused
        metadata["step"] = "manual_intervention"
        metadata["pause_reason"] = result.get("pause_reason")
        metadata["detail"] = result.get("detail")
        metadata["session_id"] = session_id
        task.task_metadata = metadata
        browser_session.status = BrowserSessionStatus.paused
        browser_session.browser_state = result.get("state", "manual_intervention")
        browser_session.pause_reason = _PAUSE_REASON_MAP.get(result.get("pause_reason"), BrowserPauseReason.unsupported_flow)
        return

    if status == "paused_question":
        task.status = WorkflowStatus.waiting_user_input
        task.current_step = "paused_question"
        application.pipeline_status = ApplicationPipelineStatus.paused
        metadata["step"] = "paused_question"
        metadata["pending_question"] = result.get("pending_question")
        metadata["session_id"] = session_id
        task.task_metadata = metadata
        browser_session.status = BrowserSessionStatus.paused
        browser_session.browser_state = result.get("state", "application")
        browser_session.pause_reason = BrowserPauseReason.question
        return

    if status == "awaiting_approval":
        task.status = WorkflowStatus.waiting_user_input
        task.current_step = "awaiting_approval"
        application.pipeline_status = ApplicationPipelineStatus.paused
        metadata["step"] = "awaiting_approval"
        metadata["session_id"] = session_id
        task.task_metadata = metadata
        browser_session.status = BrowserSessionStatus.paused
        browser_session.browser_state = "awaiting_approval"
        browser_session.pause_reason = BrowserPauseReason.user_review
        return

    # status == "submitted"
    task.status = WorkflowStatus.completed
    task.completed_at = datetime.utcnow()
    task.current_step = "submitted"
    application.pipeline_status = (
        ApplicationPipelineStatus.confirmed if result.get("confirmed") else ApplicationPipelineStatus.submitted
    )
    metadata["step"] = "submitted"
    metadata["confirmed"] = result.get("confirmed", False)
    metadata["application_id"] = result.get("application_id")
    task.task_metadata = metadata
    browser_session.status = BrowserSessionStatus.completed
    browser_session.browser_state = "submitted"


async def poll_loop() -> None:
    """Continuously poll for pending browser_submission WorkflowTasks and process them."""
    while True:
        db = SessionLocal()
        try:
            _reclaim_stale_tasks(db)

            # SKIP LOCKED makes this an atomic claim, not just a read - without
            # it, a second browser-worker replica running concurrently could
            # SELECT this same pending row before either of them commits the
            # status="running" update below, and both would process it (a
            # duplicate submission, double credential-vault mutation, or
            # corrupted checkpoint state depending on timing). Currently one
            # replica in practice, but claiming is written to be correct
            # under N replicas regardless, since nothing else in this file
            # enforces single-instance-only.
            task = (
                db.query(WorkflowTask)
                .filter(
                    WorkflowTask.status == WorkflowStatus.pending,
                    WorkflowTask.workflow_type == _WORKFLOW_TYPE,
                )
                .order_by(WorkflowTask.created_at.asc())
                .with_for_update(skip_locked=True)
                .first()
            )

            if task is None:
                await asyncio.sleep(_POLL_INTERVAL_SECONDS)
                continue

            task.status = WorkflowStatus.running
            task.started_at = datetime.utcnow()
            application = db.query(Application).filter(Application.id == task.entity_id).first()
            if application is not None:
                application.pipeline_status = ApplicationPipelineStatus.browser_running
            db.commit()

            try:
                await _run_task(task, db)
            except Exception as exc:
                logger.exception("Unhandled error processing browser_submission task %s", task.id)
                db.rollback()  # clear any partial write left by the failed operation before writing the failure
                task.status = WorkflowStatus.failed
                task.error = str(exc)
                task.retry_count = (task.retry_count or 0) + 1
                if application is not None:
                    application.pipeline_status = ApplicationPipelineStatus.failed_retryable
                browser_session = db.query(BrowserSession).filter(BrowserSession.workflow_task_id == task.id).first()
                if browser_session is not None:
                    browser_session.status = BrowserSessionStatus.failed
                    browser_session.browser_state = "failed"

            db.commit()
        finally:
            db.close()


if __name__ == "__main__":
    logger.info("Starting browser submission worker poll loop")
    asyncio.run(poll_loop())
