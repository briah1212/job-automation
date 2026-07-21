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
    application. screenshot_object_key points at MinIO, not a local path -
    filled_fields/form_state are the only large-ish payloads kept in Postgres.
    """

    __tablename__ = "browser_checkpoints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("browser_sessions.id", ondelete="CASCADE"), nullable=False, index=True)

    browser_state = Column(String, nullable=False)
    step = Column(String, nullable=False)
    url = Column(String, nullable=False)
    screenshot_object_key = Column(String, nullable=True)

    filled_fields = Column(JSONB, default=dict, nullable=False)
    form_state = Column(JSONB, default=dict, nullable=False)
    page_number = Column(Integer, default=1, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    session = relationship("BrowserSession", back_populates="checkpoints")
