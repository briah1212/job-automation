from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class ReusableAnswer(Base):
    """A pre-approved answer to a recurring application question, reusable across applications."""

    __tablename__ = "reusable_answers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    canonical_question = Column(Text, nullable=False)
    semantic_variants = Column(ARRAY(String), default=list, nullable=False)

    exact_answer = Column(Text, nullable=False)
    allowed_paraphrasing = Column(Boolean, default=False, nullable=False)
    risk_level = Column(String, nullable=False)
    categories = Column(ARRAY(String), default=list, nullable=False)

    expiration_date = Column(DateTime, nullable=True)
    user_approved = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="reusable_answers")
