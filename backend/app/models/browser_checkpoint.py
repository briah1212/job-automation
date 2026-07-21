from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class BrowserCheckpoint(Base):
    """One state-transition snapshot within a BrowserSession.

    Written before each transition's handler runs, so a crash or restart can
    resume from the last completed state instead of restarting the whole
    application. screenshot_object_key/dom_snapshot_object_key point at
    MinIO, not a local path - everything else here is small enough to live
    directly in Postgres.

    decision_reasoning/field_sources/action_log exist specifically to make a
    failed real-world run replayable without having to reproduce it live -
    "why did the state machine think this was the application page" and
    "where did this field's value actually come from" are exactly the
    questions a real ATS failure raises, and log lines scattered across a
    poll-loop's stdout are a poor substitute for a structured per-checkpoint
    record. See services/replay_report.py.
    """

    __tablename__ = "browser_checkpoints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("browser_sessions.id", ondelete="CASCADE"), nullable=False, index=True)

    browser_state = Column(String, nullable=False)
    step = Column(String, nullable=False)
    url = Column(String, nullable=False)
    screenshot_object_key = Column(String, nullable=True)
    dom_snapshot_object_key = Column(String, nullable=True)

    filled_fields = Column(JSONB, default=dict, nullable=False)
    form_state = Column(JSONB, default=dict, nullable=False)
    page_number = Column(Integer, default=1, nullable=False)

    # {"signals": {...raw signals...}, "scores": {"application": 0.8, ...}} -
    # why detect_state classified the page the way it did.
    decision_reasoning = Column(JSONB, default=dict, nullable=False)
    # {field_name: "learned_mapping" | "regex" | "answered_question" | "agent"} -
    # where each filled field's value actually came from.
    field_sources = Column(JSONB, default=dict, nullable=False)
    # [{"action": "click", "target": "...", ...}, ...] - high-level actions
    # taken to advance past this state, in order.
    action_log = Column(JSONB, default=list, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    session = relationship("BrowserSession", back_populates="checkpoints")
