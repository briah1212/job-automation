"""Job discovery via each ATS's public job-board API.

These are legitimate, publicly documented endpoints Greenhouse/Lever/Ashby
each built specifically for third-party job-board embedding - not
scraping, not bypassing anything (confirmed live against real company
boards while building this). Workday, LinkedIn, and Wellfound deliberately
aren't included yet: Workday doesn't have an equivalently simple, uniform
public API across tenants, and LinkedIn/Wellfound discovery would mean
interacting with platforms whose terms of service explicitly restrict
automated access - a materially different risk profile from a JSON API a
company deliberately publishes for exactly this purpose. That needs its
own deliberate design (and likely the user's own authenticated session),
not an extension of this module.
"""
from __future__ import annotations

import html
import logging
import re
from datetime import datetime
from typing import Any, Optional

import httpx
from sqlalchemy.orm import Session

from app.models import CanonicalJob, CompanyWatch, JobStatus, WorkflowStatus, WorkflowTask

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT_SECONDS = 15.0
_USER_AGENT = "job-automation-worker/1.0 (+https://github.com/brianhsu/job-automation)"
_HTML_TAG_RE = re.compile(r"<[^<]+?>")


def _clean_html(raw: Optional[str]) -> Optional[str]:
    """Greenhouse's `content` field is itself HTML-entity-escaped (the JSON
    string contains literal "&lt;div&gt;..." rather than real tags) - unescape
    once, then strip tags, matching backend/worker.py's own _strip_html."""
    if not raw:
        return None
    unescaped = html.unescape(raw)
    text = _HTML_TAG_RE.sub(" ", unescaped)
    return re.sub(r"\s+", " ", text).strip()


async def fetch_greenhouse_jobs(board_token: str) -> list[dict[str, Any]]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
        response = await client.get(url, headers={"User-Agent": _USER_AGENT})
        response.raise_for_status()
        data = response.json()

    return [
        {
            "external_id": str(job["id"]),
            "title": job.get("title") or "",
            "location": (job.get("location") or {}).get("name"),
            "url": job.get("absolute_url") or "",
            "raw_content": _clean_html(job.get("content")),
        }
        for job in data.get("jobs", [])
    ]


async def fetch_lever_jobs(company: str) -> list[dict[str, Any]]:
    url = f"https://api.lever.co/v0/postings/{company}?mode=json"
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
        response = await client.get(url, headers={"User-Agent": _USER_AGENT})
        response.raise_for_status()
        data = response.json()

    return [
        {
            "external_id": str(job.get("id") or ""),
            "title": job.get("text") or "",
            "location": (job.get("categories") or {}).get("location"),
            "url": job.get("hostedUrl") or "",
            "raw_content": job.get("descriptionPlain") or _clean_html(job.get("description")),
        }
        for job in data
    ]


async def fetch_ashby_jobs(board_name: str) -> list[dict[str, Any]]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{board_name}"
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
        response = await client.get(url, headers={"User-Agent": _USER_AGENT})
        response.raise_for_status()
        data = response.json()

    return [
        {
            "external_id": str(job.get("id") or ""),
            "title": job.get("title") or "",
            "location": job.get("location"),
            "url": job.get("jobUrl") or "",
            "raw_content": _clean_html(job.get("descriptionHtml")),
        }
        for job in data.get("jobs", [])
    ]


FETCHERS = {
    "greenhouse": fetch_greenhouse_jobs,
    "lever": fetch_lever_jobs,
    "ashby": fetch_ashby_jobs,
}


async def fetch_jobs_for_watch(ats_platform: str, board_identifier: str) -> list[dict[str, Any]]:
    fetcher = FETCHERS.get(ats_platform)
    if fetcher is None:
        raise ValueError(f"Unsupported ats_platform for discovery: {ats_platform!r} (supported: {sorted(FETCHERS)})")
    return await fetcher(board_identifier)


async def run_discovery_cycle(db: Session) -> dict[str, int]:
    """Poll every enabled CompanyWatch, create a CanonicalJob for each
    genuinely new posting (deduplicated by URL, scoped per user - a job
    URL is unique per posting), and enqueue the existing job_extraction
    workflow for it (reused as-is: discovery's job is finding and
    deduplicating postings, not re-implementing extraction/classification).

    One watch failing (a network error, a renamed/removed board) must not
    abort the rest of the cycle - recorded on the watch itself
    (last_poll_error) rather than raised, so a stale-slug watch doesn't
    silently block every other company from ever being polled again.
    """
    watches = db.query(CompanyWatch).filter(CompanyWatch.enabled.is_(True)).all()
    stats = {"watches_polled": 0, "watches_failed": 0, "jobs_discovered": 0}

    # Known URLs per user, fetched once per cycle (not once per watch) -
    # a URL is unique per posting regardless of which watch surfaced it.
    known_urls_by_user: dict[Any, set[str]] = {}

    for watch in watches:
        if watch.user_id not in known_urls_by_user:
            existing = db.query(CanonicalJob.extracted_data).filter(CanonicalJob.user_id == watch.user_id).all()
            known_urls_by_user[watch.user_id] = {
                row.extracted_data.get("url") for row in existing if row.extracted_data and row.extracted_data.get("url")
            }
        known_urls = known_urls_by_user[watch.user_id]

        try:
            jobs = await fetch_jobs_for_watch(watch.ats_platform, watch.board_identifier)
        except Exception as exc:
            logger.warning("Discovery failed for watch %s (%s/%s): %s", watch.id, watch.ats_platform, watch.board_identifier, exc)
            watch.last_poll_error = str(exc)
            watch.last_polled_at = datetime.utcnow()
            stats["watches_failed"] += 1
            continue

        for job in jobs:
            url = job.get("url")
            if not url or url in known_urls:
                continue
            known_urls.add(url)

            canonical_job = CanonicalJob(
                user_id=watch.user_id,
                company=watch.company_name,
                title=job.get("title") or "",
                location=job.get("location"),
                status=JobStatus.discovered,
                extracted_data={
                    "url": url,
                    "platform": watch.ats_platform,
                    "external_id": job.get("external_id"),
                    "source": "company_watch",
                    "company_watch_id": str(watch.id),
                    "raw_content": job.get("raw_content"),
                },
            )
            db.add(canonical_job)
            db.flush()

            db.add(WorkflowTask(
                workflow_type="job_extraction",
                entity_id=canonical_job.id,
                status=WorkflowStatus.pending,
            ))
            stats["jobs_discovered"] += 1

        watch.last_polled_at = datetime.utcnow()
        watch.last_poll_error = None
        stats["watches_polled"] += 1
        db.commit()

    return stats
