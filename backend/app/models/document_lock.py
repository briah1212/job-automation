from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class DocumentLock(Base):
    """A user-defined constraint that must be preserved across tailored resume variants.

    Locks apply at the resume family level so they persist across variants.
    """

    __tablename__ = "document_locks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_family_id = Column(UUID(as_uuid=True), ForeignKey("resume_families.id", ondelete="CASCADE"), nullable=False, index=True)

    lock_type = Column(String, nullable=False)
    target_ref = Column(String, nullable=False)
    value = Column(JSONB, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    resume_family = relationship("ResumeFamily")
