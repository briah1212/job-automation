from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models import (
    Application,
    ApplicationAnswer,
    ApplicationPipelineStatus,
    ApplicationQuestion,
    BrowserSession,
    ReusableAnswer,
    WorkflowStatus,
    WorkflowTask,
)
from app.services.replay_report import build_replay_report

router = APIRouter(prefix="/applications", tags=["browser-automation"])

WORKFLOW_TYPE = "browser_submission"


class AnswerPendingQuestionRequest(BaseModel):
    answer_text: str


def _get_application(application_id: uuid.UUID, current_user, db: Session) -> Application:
    application = db.query(Application).filter(
        Application.id == application_id,
        Application.user_id == current_user.id,
    ).first()
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


def _get_latest_task(application_id: uuid.UUID, db: Session) -> Optional[WorkflowTask]:
    return (
        db.query(WorkflowTask)
        .filter(WorkflowTask.workflow_type == WORKFLOW_TYPE, WorkflowTask.entity_id == application_id)
        .order_by(WorkflowTask.created_at.desc())
        .first()
    )


@router.post("/{application_id}/start-browser", status_code=status.HTTP_201_CREATED)
def start_browser_submission(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Queue a browser-automation task to fill and (with approval) submit this application."""
    application = _get_application(application_id, current_user, db)

    existing = _get_latest_task(application_id, db)
    if existing and existing.status in (WorkflowStatus.pending, WorkflowStatus.running, WorkflowStatus.waiting_user_input):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A browser submission is already in progress for this application.",
        )

    task = WorkflowTask(
        workflow_type=WORKFLOW_TYPE,
        entity_id=application_id,
        status=WorkflowStatus.pending,
        task_metadata={"step": "queued", "updated_at": datetime.utcnow().isoformat()},
    )
    db.add(task)
    application.pipeline_status = ApplicationPipelineStatus.browser_running
    db.commit()
    db.refresh(task)

    return {
        "id": str(task.id),
        "status": task.status.value,
        "task_metadata": task.task_metadata,
    }


@router.get("/{application_id}/browser-status")
def get_browser_status(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Return the latest browser-submission task's status and checkpoint data for this application."""
    _get_application(application_id, current_user, db)
    task = _get_latest_task(application_id, db)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No browser submission has been started yet")

    return {
        "id": str(task.id),
        "status": task.status.value,
        "current_step": task.current_step,
        "retry_count": task.retry_count,
        "error": task.error,
        "task_metadata": task.task_metadata,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
    }


@router.post("/{application_id}/approve-submit")
def approve_submit(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Approve the recorded submission preview so the worker proceeds to actually click submit."""
    _get_application(application_id, current_user, db)
    task = _get_latest_task(application_id, db)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No browser submission has been started yet")

    metadata = dict(task.task_metadata or {})
    if task.status != WorkflowStatus.waiting_user_input or metadata.get("step") != "awaiting_approval":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This application is not currently awaiting submission approval.",
        )

    metadata["step"] = "approved_for_submit"
    metadata["updated_at"] = datetime.utcnow().isoformat()
    task.task_metadata = metadata
    task.status = WorkflowStatus.pending
    db.commit()
    db.refresh(task)

    return {"id": str(task.id), "status": task.status.value, "task_metadata": task.task_metadata}


@router.post("/{application_id}/resume-manual-intervention")
def resume_manual_intervention(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Resume a session paused for manual intervention (CAPTCHA, MFA, email
    verification, login failure, missing document, or any other reason the
    worker couldn't proceed automatically) after the user has handled it.

    Generic on purpose: this doesn't know or care what kind of intervention
    was needed, only that the task is currently paused for one. The worker's
    resume() picks the right strategy (structural vs. replay) based on the
    BrowserState of the last real checkpoint, not anything this endpoint sets.
    """
    _get_application(application_id, current_user, db)
    task = _get_latest_task(application_id, db)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No browser submission has been started yet")

    metadata = dict(task.task_metadata or {})
    if task.status != WorkflowStatus.waiting_user_input or metadata.get("step") != "manual_intervention":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This application is not currently paused for manual intervention.",
        )

    metadata["step"] = "manual_intervention_resumed"
    metadata["updated_at"] = datetime.utcnow().isoformat()
    task.task_metadata = metadata
    task.status = WorkflowStatus.pending
    db.commit()
    db.refresh(task)

    return {"id": str(task.id), "status": task.status.value, "task_metadata": task.task_metadata}


@router.post("/{application_id}/answer-pending-question")
def answer_pending_question(
    application_id: uuid.UUID,
    body: AnswerPendingQuestionRequest,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Answer a question the worker paused on, so it can resume and store the answer for future reuse."""
    _get_application(application_id, current_user, db)
    task = _get_latest_task(application_id, db)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No browser submission has been started yet")

    metadata = dict(task.task_metadata or {})
    pending_question = metadata.get("pending_question")
    if task.status != WorkflowStatus.waiting_user_input or metadata.get("step") != "paused_question" or not pending_question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This application is not currently paused on an unanswered question.",
        )

    question = ApplicationQuestion(
        application_id=application_id,
        question_text=pending_question.get("label", ""),
        question_type=pending_question.get("question_type", "custom"),
        risk_level=pending_question.get("risk_level", "medium"),
    )
    db.add(question)
    db.flush()
    answer = ApplicationAnswer(
        application_question_id=question.id,
        answer_text=body.answer_text,
        source="user_input",
        approved=True,
    )
    db.add(answer)

    # A human directly typed and is submitting this answer for a real
    # application right now - that's exactly the approval bar this table
    # already requires (user_approved=True), so it becomes available to
    # find_matching_reusable_answer for every future application immediately,
    # not just this one. This is what actually makes "learned once, reused
    # forever" true for dynamic questions, not just for form field mappings.
    if pending_question.get("label"):
        db.add(ReusableAnswer(
            user_id=current_user.id,
            canonical_question=pending_question["label"],
            exact_answer=body.answer_text,
            risk_level=pending_question.get("risk_level", "medium"),
            user_approved=True,
        ))

    metadata["step"] = "question_answered"
    metadata["pending_question"] = None
    metadata["last_answer"] = {
        "label": pending_question.get("label", ""),
        "field_name": pending_question.get("field_name"),
        "answer_text": body.answer_text,
    }
    metadata["updated_at"] = datetime.utcnow().isoformat()
    task.task_metadata = metadata
    task.status = WorkflowStatus.pending
    db.commit()
    db.refresh(task)

    return {"id": str(task.id), "status": task.status.value, "task_metadata": task.task_metadata}


@router.post("/{application_id}/cancel-browser")
def cancel_browser_submission(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Cancel an in-progress or paused browser submission."""
    application = _get_application(application_id, current_user, db)
    task = _get_latest_task(application_id, db)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No browser submission has been started yet")

    task.status = WorkflowStatus.cancelled
    task.completed_at = datetime.utcnow()
    application.pipeline_status = ApplicationPipelineStatus.draft
    db.commit()
    db.refresh(task)

    return {"id": str(task.id), "status": task.status.value}


@router.get("/{application_id}/replay", response_class=HTMLResponse)
def get_replay_report(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> str:
    """A self-contained HTML timeline of every checkpoint this application's
    browser session went through - screenshot, DOM snapshot, why each state
    was detected, where each field's value came from, and every action
    taken, in order. Built specifically so a real-world failure doesn't need
    to be reproduced live to understand - see app.services.replay_report."""
    _get_application(application_id, current_user, db)
    browser_session = (
        db.query(BrowserSession)
        .filter(BrowserSession.application_id == application_id)
        .order_by(BrowserSession.created_at.desc())
        .first()
    )
    if browser_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No browser session found for this application")

    return build_replay_report(db, browser_session.id)
