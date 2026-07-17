from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class DocumentRendering(Base):
    """A rendered file (PDF/DOCX) for a resume version."""

    __tablename__ = "document_renderings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_version_id = Column(UUID(as_uuid=True), ForeignKey("resume_versions.id", ondelete="CASCADE"), nullable=False, index=True)

    format = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    page_count = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    resume_version = relationship("ResumeVersion")
