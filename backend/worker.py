"""Background polling worker for DB-backed workflow tasks.

This is a deliberate, spec-sanctioned substitute for a full workflow engine
(e.g. Temporal): a lightweight polling loop that claims pending WorkflowTask
rows and processes them, while preserving a clean interface (process_*
functions keyed by workflow_type) that would allow migrating to a real
workflow engine later without rewriting the underlying business logic.

Currently handles the "job_extraction" workflow: fetching a job posting's raw
HTML, stripping it down to plain text, running it through the extraction and
classification agents, and writing the results back onto the CanonicalJob.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.agents.classification_agent import ClassificationAgent
from app.agents.extraction_agent import ExtractionAgent
from app.core.database import SessionLocal
from app.models import CanonicalJob, JobStatus, WorkflowStatus, WorkflowTask
from app.services.seniority_heuristic import infer_seniority

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_HTTP_TIMEOUT_SECONDS = 10.0
_USER_AGENT = "job-automation-worker/1.0 (+https://github.com/brianhsu/job-automation)"
_MAX_DESCRIPTION_CHARS = 5000
_POLL_INTERVAL_SECONDS = 5

_HTML_TAG_RE = re.compile(r"<[^<]+?>")


def _strip_html(html: str) -> str:
    """Strip HTML tags down to plain text using a lightweight regex (no BeautifulSoup dependency)."""
    text = _HTML_TAG_RE.sub(" ", html)
    # Collapse excess whitespace left behind by stripped tags/newlines.
    return re.sub(r"\s+", " ", text).strip()


async def _fetch_raw_text(url: str) -> tuple[str, bool]:
    """Fetch a job posting URL and return (plain_text, fetch_succeeded).

    On any fetch failure (timeout, connection error, non-200 status), logs a
    warning and returns a minimal fallback (just the URL) rather than raising,
    so the extraction pipeline doesn't get stuck on an unreachable page.
    """
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers={"User-Agent": _USER_AGENT})
            response.raise_for_status()
            return _strip_html(response.text), True
    except Exception as exc:
        logger.warning("Failed to fetch job posting URL %s: %s", url, exc)
        return url, False


async def process_extraction_task(task: WorkflowTask, db: Session) -> None:
    """Process a single job_extraction WorkflowTask: fetch, extract, classify, persist."""
    try:
        job = db.query(CanonicalJob).filter(CanonicalJob.id == task.entity_id).first()
        if job is None:
            raise ValueError(f"CanonicalJob {task.entity_id} not found")

        extracted_data = dict(job.extracted_data or {})
        url = extracted_data.get("url")

        fetch_succeeded = False
        if url:
            raw_text, fetch_succeeded = await _fetch_raw_text(url)
        else:
            raw_text = ""

        if not fetch_succeeded:
            extracted_data["fetch_warning"] = (
                f"Could not fetch job posting content from {url}; "
                "extraction proceeded with minimal/no page content."
            )

        user_id = str(job.user_id)

        extracted = await ExtractionAgent().extract(
            raw_text=raw_text,
            source_url=url,
            user_id=user_id,
        )
        classification = await ClassificationAgent().classify(
            title=extracted.get("title") or "",
            responsibilities=extracted.get("responsibilities") or [],
            user_id=user_id,
        )

        # Only overwrite existing columns with non-empty extracted values.
        if extracted.get("company"):
            job.company = extracted["company"]
        if extracted.get("title"):
            job.title = extracted["title"]
        if extracted.get("location"):
            job.location = extracted["location"]
        if extracted.get("remote_policy"):
            job.remote_policy = extracted["remote_policy"]
        if extracted.get("salary_min") is not None:
            job.salary_min = extracted["salary_min"]
        if extracted.get("salary_max") is not None:
            job.salary_max = extracted["salary_max"]

        if not job.description and raw_text:
            job.description = raw_text[:_MAX_DESCRIPTION_CHARS]

        required_skills = extracted.get("required_skills") or []
        preferred_skills = extracted.get("preferred_skills") or []
        skills = list(dict.fromkeys([*required_skills, *preferred_skills]))

        extracted_data.update({
            "url": url,
            "skills": skills,
            "requirements": extracted.get("responsibilities") or [],
            "category": classification.get("primary_category", ""),
            "secondary_categories": classification.get("secondary_categories", []),
            "seniority_level": infer_seniority(
                extracted.get("title") or "", extracted.get("experience_years_min")
            ),
            "raw_text_length": len(raw_text),
        })
        job.extracted_data = extracted_data

        # Extraction produced real data (company + title) - move the job forward.
        # Otherwise leave it in `extracting` (rather than a fabricated status like
        # "needs_enrichment", which isn't in JobStatus) so it's clear it's still
        # awaiting usable data; the fetch/extraction warning is recorded above.
        if job.company and job.title:
            job.status = JobStatus.scored

        task.status = WorkflowStatus.completed
        task.completed_at = datetime.utcnow()

    except Exception as exc:
        logger.exception("Failed to process job_extraction task %s", task.id)
        task.status = WorkflowStatus.failed
        task.error = str(exc)
        task.retry_count = (task.retry_count or 0) + 1


async def poll_loop() -> None:
    """Continuously poll for pending job_extraction WorkflowTasks and process them."""
    while True:
        db = SessionLocal()
        try:
            task = (
                db.query(WorkflowTask)
                .filter(
                    WorkflowTask.status == WorkflowStatus.pending,
                    WorkflowTask.workflow_type == "job_extraction",
                )
                .order_by(WorkflowTask.created_at.asc())
                .first()
            )

            if task is None:
                await asyncio.sleep(_POLL_INTERVAL_SECONDS)
                continue

            task.status = WorkflowStatus.running
            task.started_at = datetime.utcnow()
            db.commit()

            try:
                await process_extraction_task(task, db)
            except Exception:
                logger.exception("Unhandled error processing task %s; continuing poll loop", task.id)

            db.commit()
        finally:
            db.close()


if __name__ == "__main__":
    logger.info("Starting job extraction worker poll loop")
    asyncio.run(poll_loop())
