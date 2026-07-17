from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class ProfileFact(Base):
    """A single atomic fact about a user's career history, used as source material for tailoring."""

    __tablename__ = "profile_facts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    fact_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)

    source_type = Column(String, nullable=False)
    source_identifier = Column(String, nullable=True)
    original_text = Column(Text, nullable=True)

    confidence = Column(Float, default=1.0, nullable=False)
    user_verified = Column(Boolean, default=False, nullable=False)

    permitted_uses = Column(ARRAY(String), default=list, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="profile_facts")
