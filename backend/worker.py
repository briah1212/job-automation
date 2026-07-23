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
import html as html_lib
import logging
import os
import re
import time
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.agents.classification_agent import ClassificationAgent
from app.agents.extraction_agent import ExtractionAgent
from app.core.database import SessionLocal
from app.models import CanonicalJob, JobStatus, WorkflowStatus, WorkflowTask
from app.services.job_discovery import run_discovery_cycle
from app.services.seniority_heuristic import infer_seniority

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_HTTP_TIMEOUT_SECONDS = 10.0
_USER_AGENT = "job-automation-worker/1.0 (+https://github.com/brianhsu/job-automation)"
_MAX_DESCRIPTION_CHARS = 5000
_POLL_INTERVAL_SECONDS = 5

# browser-worker's render_server.py (see that module's docstring) - a plain
# httpx GET has no JS engine at all, so a client-rendered SPA (confirmed
# live, repeatedly: Ashby's job board, a Workday-hosted posting) comes back
# as a near-empty shell or literally nothing. This container has no browser
# dependency of its own; browser-worker already does, for application
# automation, so extraction reuses that instead of installing a second one.
_RENDER_SERVER_URL = os.environ.get("BROWSER_WORKER_RENDER_URL", "http://browser-worker:8100")
_INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")
_RENDER_TIMEOUT_SECONDS = 30.0
# Below this, treat the httpx fetch's result as "probably needed JS" rather
# than "genuinely a short page" - calibrated against real examples this
# session: an SPA's unrendered shell text ("You need to enable JavaScript
# to run this app.") is 91 chars; every genuine job posting fetched
# successfully this session was several thousand.
_THIN_CONTENT_CHARS = 300
# Discovery hits real third-party APIs, so it runs far less often than the
# task poll - every 15 minutes is frequent enough to catch new postings
# same-day without hammering Greenhouse/Lever/Ashby's public endpoints.
_DISCOVERY_INTERVAL_SECONDS = 900

_HTML_TAG_RE = re.compile(r"<[^<]+?>")
# Strips <script>/<style> elements *and their contents*, not just the tags -
# the generic tag-stripper below only removes markup, so a page with a large
# inline <style> block (confirmed live on a real Lever posting: several KB of
# @font-face/CSS) left raw CSS source sitting in the "plain text" output,
# pushing the real job content past _MAX_DESCRIPTION_CHARS/the extraction
# agent's own truncation entirely. Only the page <title> (always near the
# very top of <head>, before any <style> block) survived - explaining company
# and title extracting correctly while everything else (skills, salary,
# requirements) came back empty from an LLM that never actually saw them.
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)


def _strip_html(raw_html: str) -> str:
    """Strip HTML tags down to plain text using a lightweight regex (no BeautifulSoup dependency).

    Real job postings routinely contain entities (&amp;, &hellip;, &rarr;, ...)
    for characters like &, ..., ->  - unescape those before stripping tags so
    they render as the real character instead of literal entity text (matches
    job_discovery.py's _clean_html, which does the same for the ATS-API path).
    """
    without_script_style = _SCRIPT_STYLE_RE.sub(" ", raw_html)
    text = _HTML_TAG_RE.sub(" ", html_lib.unescape(without_script_style))
    # Collapse excess whitespace left behind by stripped tags/newlines.
    return re.sub(r"\s+", " ", text).strip()


async def _fetch_via_browser(url: str) -> tuple[str, bool]:
    """Fall back to browser-worker's render_server.py for a URL whose plain
    HTTP fetch came back empty/thin - see _RENDER_SERVER_URL's comment."""
    try:
        async with httpx.AsyncClient(timeout=_RENDER_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{_RENDER_SERVER_URL}/render",
                headers={"X-Internal-Api-Key": _INTERNAL_API_KEY},
                json={"url": url},
            )
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.warning("Browser-render fallback failed for %s: %s", url, exc)
        return "", False

    if not data.get("success"):
        logger.warning("Browser-render fallback reported failure for %s: %s", url, data.get("error"))
        return "", False

    # Already plain visible text (render_server.py strips script/style
    # itself) - just collapse whitespace, matching _strip_html's own tail.
    text = re.sub(r"\s+", " ", data.get("text") or "").strip()
    return text, bool(text)


async def _fetch_raw_text(url: str) -> tuple[str, bool]:
    """Fetch a job posting URL and return (plain_text, fetch_succeeded).

    On any fetch failure (timeout, connection error, non-200 status), logs a
    warning and returns a minimal fallback (just the URL) rather than raising,
    so the extraction pipeline doesn't get stuck on an unreachable page.

    Tries a plain HTTP fetch first (cheap, fast, sufficient for most sites),
    and only falls back to a real browser render (_fetch_via_browser) when
    that comes back empty or suspiciously thin - most job postings don't
    need a browser at all, so paying Chromium's cost on every single fetch
    would be wasteful.
    """
    try:
        # httpx defaults to NOT following redirects, and raise_for_status()
        # treats an unfollowed redirect as an error - so without this, any
        # URL that 301/302s (trailing-slash normalization, an expired
        # Greenhouse job id redirecting to the company's live careers page,
        # etc.) silently produced zero real content instead of the page
        # actually at the other end of a completely ordinary redirect.
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": _USER_AGENT})
            response.raise_for_status()
            text = _strip_html(response.text)
    except Exception as exc:
        logger.warning("Failed to fetch job posting URL %s: %s", url, exc)
        text = ""

    if len(text) >= _THIN_CONTENT_CHARS:
        return text, True

    logger.info(
        "Plain HTTP fetch for %s returned only %d chars - falling back to browser render",
        url, len(text),
    )
    rendered_text, rendered_success = await _fetch_via_browser(url)
    if rendered_success:
        return rendered_text, True

    # Neither approach got real content - keep whatever thin/empty text the
    # plain fetch produced (still better than nothing) rather than losing it.
    return text or url, bool(text)


async def process_extraction_task(task: WorkflowTask, db: Session) -> None:
    """Process a single job_extraction WorkflowTask: fetch, extract, classify, persist."""
    try:
        job = db.query(CanonicalJob).filter(CanonicalJob.id == task.entity_id).first()
        if job is None:
            raise ValueError(f"CanonicalJob {task.entity_id} not found")

        extracted_data = dict(job.extracted_data or {})
        url = extracted_data.get("url")

        # Discovery (job_discovery.py) already pulls clean description text
        # straight from the ATS's own public API when it creates this job -
        # reusing it here means real extraction quality for a discovered
        # job, instead of either an httpx GET of a JS-rendered SPA shell
        # (Ashby, Lever) or a redundant second fetch of a page discovery
        # already had the real content for.
        pre_fetched = extracted_data.get("raw_content")
        if pre_fetched:
            raw_text, fetch_succeeded = pre_fetched, True
        elif url:
            raw_text, fetch_succeeded = await _fetch_raw_text(url)
        else:
            raw_text, fetch_succeeded = "", False

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
            title=job.title or extracted.get("title") or "",
            responsibilities=extracted.get("responsibilities") or [],
            user_id=user_id,
        )

        # A job discovered via a company watch already has authoritative
        # company/title/location straight from the ATS's own structured API
        # (see job_discovery.py) - the extraction agent's job for these is
        # everything ELSE (skills, requirements, seniority), not
        # re-guessing facts already known for certain. Without this, a
        # mock/weak extraction call can silently clobber real data with a
        # worse guess (caught live: every discovered job's real company/
        # title got overwritten with AI_PROVIDER=mock's fixed canned
        # response, "Acme Corp" / "Senior Data Engineer", regardless of
        # which real company or posting it actually was).
        from_authoritative_source = extracted_data.get("source") == "company_watch"

        # Only overwrite existing columns with non-empty extracted values.
        if extracted.get("company") and not from_authoritative_source:
            job.company = extracted["company"]
        if extracted.get("title") and not from_authoritative_source:
            job.title = extracted["title"]
        if extracted.get("location") and not from_authoritative_source:
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
                job.title or extracted.get("title") or "", extracted.get("experience_years_min")
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
    """Continuously poll for pending job_extraction WorkflowTasks and process
    them, and periodically run job discovery across every enabled
    CompanyWatch (see _DISCOVERY_INTERVAL_SECONDS) - one process, two
    independent cadences: task-polling stays fast (5s) since it's reacting
    to work already queued, discovery stays slow (15min) since it's the one
    making outbound calls to real third-party APIs."""
    last_discovery_at = 0.0
    while True:
        db = SessionLocal()
        try:
            now = time.monotonic()
            if now - last_discovery_at >= _DISCOVERY_INTERVAL_SECONDS:
                last_discovery_at = now
                try:
                    stats = await run_discovery_cycle(db)
                    logger.info("Discovery cycle complete: %s", stats)
                except Exception:
                    logger.exception("Unhandled error running discovery cycle; continuing poll loop")

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
