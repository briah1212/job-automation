from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class CompanyWatch(Base):
    """A company's public ATS job board to poll for new postings (Phase 6: Discovery Automation).

    board_identifier is the slug/token the ATS's own public job-board API
    uses to identify the company (e.g. Greenhouse's "board_token", Lever's
    company slug, Ashby's "board_name") - not a URL, since each platform's
    API takes just the identifier.
    """

    __tablename__ = "company_watches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    company_name = Column(String, nullable=False)
    ats_platform = Column(String, nullable=False)
    board_identifier = Column(String, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)

    last_polled_at = Column(DateTime, nullable=True)
    last_poll_error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="company_watches")
