from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class ApplicationReview(Base):
    """An automated compliance/quality review pass over an application before submission."""

    __tablename__ = "application_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)

    passed = Column(Boolean, nullable=False)
    blocking_findings = Column(JSONB, default=list, nullable=False)
    warnings = Column(JSONB, default=list, nullable=False)
    confidence = Column(Float, nullable=False)
    recommended_correction = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    application = relationship("Application")
