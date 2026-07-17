from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class CoverLetter(Base):
    """A generated cover letter draft tied to an application."""

    __tablename__ = "cover_letters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)

    content = Column(Text, nullable=False)
    tone = Column(String, nullable=True)
    word_limit = Column(Integer, nullable=True)
    word_count = Column(Integer, nullable=True)

    status = Column(String, nullable=False)
    warnings = Column(JSONB, default=list, nullable=False)
    claim_provenance = Column(JSONB, default=list, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    application = relationship("Application", back_populates="cover_letters")
