from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class ApplicationQuestion(Base):
    """A question encountered on an application form."""

    __tablename__ = "application_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)

    question_text = Column(Text, nullable=False)
    question_type = Column(String, nullable=False)
    risk_level = Column(String, nullable=False)

    canonical_reusable_answer_id = Column(
        UUID(as_uuid=True), ForeignKey("reusable_answers.id", ondelete="SET NULL"), nullable=True
    )

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    application = relationship("Application")
    canonical_reusable_answer = relationship("ReusableAnswer")
    answer = relationship("ApplicationAnswer", back_populates="application_question", uselist=False, cascade="all, delete-orphan")
