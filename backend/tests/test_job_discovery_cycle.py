"""Tests for run_discovery_cycle's dedup/creation logic against a real
Postgres test DB (per conftest.py's `db` fixture) - fetch_jobs_for_watch
itself is monkeypatched so these don't hit the real network."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.models import CanonicalJob, CompanyWatch, JobStatus, User, WorkflowStatus, WorkflowTask
from app.services.job_discovery import run_discovery_cycle


def _make_user(db) -> User:
    user = User(id=uuid.uuid4(), email=f"discovery-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_watch(db, user, **kwargs) -> CompanyWatch:
    watch = CompanyWatch(
        user_id=user.id,
        company_name=kwargs.get("company_name", "Airtable"),
        ats_platform=kwargs.get("ats_platform", "greenhouse"),
        board_identifier=kwargs.get("board_identifier", "airtable"),
        enabled=kwargs.get("enabled", True),
    )
    db.add(watch)
    db.commit()
    db.refresh(watch)
    return watch


_FAKE_JOBS = [
    {"external_id": "1", "title": "Software Engineer", "location": "NYC", "url": "https://example.com/jobs/1", "raw_content": "desc 1"},
    {"external_id": "2", "title": "Data Engineer", "location": "Remote", "url": "https://example.com/jobs/2", "raw_content": "desc 2"},
]


@pytest.mark.asyncio
async def test_discovery_creates_jobs_and_extraction_tasks(db):
    user = _make_user(db)
    _make_watch(db, user)

    with patch("app.services.job_discovery.fetch_jobs_for_watch", new=AsyncMock(return_value=_FAKE_JOBS)):
        stats = await run_discovery_cycle(db)

    assert stats == {"watches_polled": 1, "watches_failed": 0, "jobs_discovered": 2}

    jobs = db.query(CanonicalJob).filter(CanonicalJob.user_id == user.id).all()
    assert len(jobs) == 2
    assert {j.title for j in jobs} == {"Software Engineer", "Data Engineer"}
    assert all(j.status == JobStatus.discovered for j in jobs)

    tasks = db.query(WorkflowTask).filter(WorkflowTask.workflow_type == "job_extraction").all()
    assert len(tasks) == 2
    assert all(t.status == WorkflowStatus.pending for t in tasks)
    assert {t.entity_id for t in tasks} == {j.id for j in jobs}


@pytest.mark.asyncio
async def test_discovery_does_not_recreate_already_known_jobs(db):
    """Second cycle with the same jobs must add nothing new - dedup by URL."""
    user = _make_user(db)
    _make_watch(db, user)

    with patch("app.services.job_discovery.fetch_jobs_for_watch", new=AsyncMock(return_value=_FAKE_JOBS)):
        await run_discovery_cycle(db)
        stats_second = await run_discovery_cycle(db)

    assert stats_second["jobs_discovered"] == 0
    jobs = db.query(CanonicalJob).filter(CanonicalJob.user_id == user.id).all()
    assert len(jobs) == 2


@pytest.mark.asyncio
async def test_discovery_only_adds_genuinely_new_jobs_on_partial_overlap(db):
    user = _make_user(db)
    _make_watch(db, user)

    with patch("app.services.job_discovery.fetch_jobs_for_watch", new=AsyncMock(return_value=_FAKE_JOBS)):
        await run_discovery_cycle(db)

    new_job = {"external_id": "3", "title": "Platform Engineer", "location": "NYC", "url": "https://example.com/jobs/3", "raw_content": "desc 3"}
    with patch("app.services.job_discovery.fetch_jobs_for_watch", new=AsyncMock(return_value=[*_FAKE_JOBS, new_job])):
        stats = await run_discovery_cycle(db)

    assert stats["jobs_discovered"] == 1
    jobs = db.query(CanonicalJob).filter(CanonicalJob.user_id == user.id).all()
    assert len(jobs) == 3


@pytest.mark.asyncio
async def test_discovery_skips_disabled_watches(db):
    user = _make_user(db)
    _make_watch(db, user, enabled=False)

    fetch_mock = AsyncMock(return_value=_FAKE_JOBS)
    with patch("app.services.job_discovery.fetch_jobs_for_watch", new=fetch_mock):
        stats = await run_discovery_cycle(db)

    fetch_mock.assert_not_called()
    assert stats == {"watches_polled": 0, "watches_failed": 0, "jobs_discovered": 0}


@pytest.mark.asyncio
async def test_discovery_records_error_and_continues_other_watches(db):
    user = _make_user(db)
    failing_watch = _make_watch(db, user, company_name="Broken Co", board_identifier="broken")
    working_watch = _make_watch(db, user, company_name="Airtable", board_identifier="airtable")

    async def fake_fetch(ats_platform, board_identifier):
        if board_identifier == "broken":
            raise RuntimeError("board not found")
        return _FAKE_JOBS

    with patch("app.services.job_discovery.fetch_jobs_for_watch", new=AsyncMock(side_effect=fake_fetch)):
        stats = await run_discovery_cycle(db)

    assert stats["watches_failed"] == 1
    assert stats["watches_polled"] == 1
    assert stats["jobs_discovered"] == 2

    db.refresh(failing_watch)
    db.refresh(working_watch)
    assert failing_watch.last_poll_error == "board not found"
    assert working_watch.last_poll_error is None
    assert working_watch.last_polled_at is not None


@pytest.mark.asyncio
async def test_discovery_dedup_is_scoped_per_user(db):
    """Two different users watching the same board must each get their own
    CanonicalJob rows - discovered jobs aren't shared across accounts."""
    user_a = _make_user(db)
    user_b = _make_user(db)
    _make_watch(db, user_a)
    _make_watch(db, user_b)

    with patch("app.services.job_discovery.fetch_jobs_for_watch", new=AsyncMock(return_value=_FAKE_JOBS)):
        stats = await run_discovery_cycle(db)

    assert stats["jobs_discovered"] == 4
    assert db.query(CanonicalJob).filter(CanonicalJob.user_id == user_a.id).count() == 2
    assert db.query(CanonicalJob).filter(CanonicalJob.user_id == user_b.id).count() == 2
