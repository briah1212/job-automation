"""Tests for build_replay_report - the debug/replay HTML timeline.

Deliberately doesn't exercise the MinIO screenshot/DOM-snapshot fetch path
(covered live, not worth a MinIO dependency in a fast unit test) - checkpoints
here have no object keys, which _fetch_bytes_safe already handles by
degrading to "not captured" placeholders rather than raising.
"""
from __future__ import annotations

import uuid

import pytest

from app.models import (
    Application,
    ApplicationPipelineStatus,
    ApplicationStatus,
    BrowserCheckpoint,
    BrowserPauseReason,
    BrowserSession,
    BrowserSessionStatus,
    CanonicalJob,
    JobStatus,
    User,
    WorkflowStatus,
    WorkflowTask,
)
from app.services.replay_report import build_replay_report


def _make_browser_session(db) -> BrowserSession:
    user = User(id=uuid.uuid4(), email=f"replaytest-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x")
    db.add(user)
    db.flush()
    job = CanonicalJob(
        id=uuid.uuid4(), user_id=user.id, title="Test Role", company="Test Co",
        status=JobStatus.discovered, extracted_data={"url": "http://example.com"},
    )
    db.add(job)
    db.flush()
    application = Application(
        id=uuid.uuid4(), user_id=user.id, job_id=job.id,
        status=ApplicationStatus.draft, pipeline_status=ApplicationPipelineStatus.browser_running,
    )
    db.add(application)
    db.flush()
    task = WorkflowTask(
        id=uuid.uuid4(), workflow_type="browser_submission", entity_id=application.id,
        status=WorkflowStatus.running, task_metadata={},
    )
    db.add(task)
    db.flush()
    session = BrowserSession(
        application_id=application.id, workflow_task_id=task.id,
        session_key=f"test-{uuid.uuid4().hex[:8]}", browser_state="queued", status=BrowserSessionStatus.active,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def test_report_for_session_with_no_checkpoints(db):
    session = _make_browser_session(db)
    report = build_replay_report(db, session.id)
    assert session.session_key in report
    assert "No checkpoints recorded" in report


def test_report_raises_for_unknown_session(db):
    with pytest.raises(ValueError):
        build_replay_report(db, uuid.uuid4())


def test_report_renders_checkpoints_in_order_with_reasoning_and_sources(db):
    session = _make_browser_session(db)
    db.add(BrowserCheckpoint(
        session_id=session.id, browser_state="landing", step="landing", url="http://example.com/",
        filled_fields={}, form_state={}, page_number=1,
        decision_reasoning={"scores": {"landing": 0.9}}, field_sources={}, action_log=[],
    ))
    db.add(BrowserCheckpoint(
        session_id=session.id, browser_state="application", step="application", url="http://example.com/apply",
        filled_fields={"first_name": "Jane"}, form_state={}, page_number=1,
        decision_reasoning={"scores": {"application": 0.8}},
        field_sources={"first_name": "learned_mapping"},
        action_log=[{"action": "handle_state", "state": "application", "success": True}],
    ))
    db.commit()

    report = build_replay_report(db, session.id)

    assert report.index("landing") < report.index('id="checkpoint-2"')
    assert "learned_mapping" in report
    assert "handle_state" in report
    assert "Jane" in report
    assert 'id="checkpoint-1"' in report and 'id="checkpoint-2"' in report


def test_report_shows_pause_reason_when_session_paused(db):
    session = _make_browser_session(db)
    session.status = BrowserSessionStatus.paused
    session.pause_reason = BrowserPauseReason.captcha
    db.commit()

    report = build_replay_report(db, session.id)
    assert "captcha" in report


def test_report_degrades_gracefully_with_no_object_storage_available(db):
    """Checkpoints with no screenshot/DOM object keys (or an unreachable
    MinIO) must render a placeholder, not raise."""
    session = _make_browser_session(db)
    db.add(BrowserCheckpoint(
        session_id=session.id, browser_state="landing", step="landing", url="http://example.com/",
        filled_fields={}, form_state={}, page_number=1,
        screenshot_object_key=None, dom_snapshot_object_key=None,
    ))
    db.commit()

    report = build_replay_report(db, session.id)
    assert "No screenshot captured" in report
    assert "No DOM snapshot captured" in report
