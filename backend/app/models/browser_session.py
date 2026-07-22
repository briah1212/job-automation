from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class BrowserSessionStatus(str, enum.Enum):
    """Lifecycle status of a browser automation session."""
    active = "active"
    paused = "paused"
    completed = "completed"
    failed = "failed"
    abandoned = "abandoned"


class BrowserPauseReason(str, enum.Enum):
    """Why a session transitioned into MANUAL_INTERVENTION."""
    captcha = "captcha"
    mfa = "mfa"
    email_verification = "email_verification"
    unsupported_flow = "unsupported_flow"
    repeated_failure = "repeated_failure"
    user_review = "user_review"
    question = "question"


class BrowserSession(Base):
    """A durable record of one browser-automation attempt at an application.

    browser_state is stored as a plain string, not a DB-level enum, because the
    BrowserState enum is owned by browser_worker (a separate process/package) -
    keeping it a string avoids a second, migration-managed copy of that enum
    drifting out of sync with the one browser_worker actually uses.
    """

    __tablename__ = "browser_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_task_id = Column(UUID(as_uuid=True), ForeignKey("workflow_tasks.id", ondelete="CASCADE"), nullable=False, index=True)

    session_key = Column(String, nullable=False, unique=True, index=True)
    browser_state = Column(String, nullable=False)
    ats_platform = Column(String, nullable=True)
    tenant_key = Column(String, nullable=True)

    status = Column(Enum(BrowserSessionStatus), nullable=False, index=True)
    pause_reason = Column(Enum(BrowserPauseReason), nullable=True)

    # Playwright storage_state (cookies + localStorage) captured at the end
    # of every run/resume - lets a later resume() restore real session
    # state instead of always starting from a brand-new, cookie-less
    # browser. Not encrypted at rest (unlike AtsCredential, which browser-
    # worker never decrypts itself): browser-worker is the only process
    # that ever needs the plaintext value, and it already has direct DB
    # access for checkpoint data of comparable sensitivity (filled_fields,
    # form_state). A real hardening pass would want this encrypted the
    # same way credentials are - tracked as a known gap, not fixed here.
    storage_state = Column(JSONB, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    application = relationship("Application")
    workflow_task = relationship("WorkflowTask")
    checkpoints = relationship("BrowserCheckpoint", back_populates="session", cascade="all, delete-orphan", order_by="BrowserCheckpoint.created_at")
