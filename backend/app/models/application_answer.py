from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class ApplicationAnswer(Base):
    """The final answer submitted for an application question (one per question)."""

    __tablename__ = "application_answers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("application_questions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    answer_text = Column(Text, nullable=False)
    source = Column(String, nullable=False)
    approved = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    application_question = relationship("ApplicationQuestion", back_populates="answer")
    sources = relationship("ApplicationAnswerSource", back_populates="application_answer", cascade="all, delete-orphan")


class ApplicationAnswerSource(Base):
    """Links an application answer back to the profile fact(s) that support it."""

    __tablename__ = "application_answer_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_answer_id = Column(
        UUID(as_uuid=True), ForeignKey("application_answers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_fact_id = Column(UUID(as_uuid=True), ForeignKey("profile_facts.id", ondelete="SET NULL"), nullable=True)

    explanation = Column(Text, nullable=True)

    # Relationships
    application_answer = relationship("ApplicationAnswer", back_populates="sources")
    profile_fact = relationship("ProfileFact")
