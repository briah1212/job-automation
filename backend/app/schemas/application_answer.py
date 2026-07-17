from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ApplicationAnswerBase(BaseModel):
    """Base application answer schema."""
    answer_text: str
    source: str
    approved: bool = False


class ApplicationAnswerCreate(ApplicationAnswerBase):
    """Application answer creation schema."""
    application_question_id: UUID


class ApplicationAnswer(ApplicationAnswerBase):
    """Application answer response schema."""
    id: UUID
    application_question_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApplicationAnswerSourceBase(BaseModel):
    """Base application answer source schema."""
    explanation: Optional[str] = None


class ApplicationAnswerSourceCreate(ApplicationAnswerSourceBase):
    """Application answer source creation schema."""
    application_answer_id: UUID
    profile_fact_id: Optional[UUID] = None


class ApplicationAnswerSource(ApplicationAnswerSourceBase):
    """Application answer source response schema."""
    id: UUID
    application_answer_id: UUID
    profile_fact_id: Optional[UUID]

    model_config = {"from_attributes": True}
