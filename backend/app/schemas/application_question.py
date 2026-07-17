from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ApplicationQuestionBase(BaseModel):
    """Base application question schema."""
    question_text: str
    question_type: str
    risk_level: str
    canonical_reusable_answer_id: Optional[UUID] = None


class ApplicationQuestionCreate(ApplicationQuestionBase):
    """Application question creation schema."""
    application_id: UUID


class ApplicationQuestion(ApplicationQuestionBase):
    """Application question response schema."""
    id: UUID
    application_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}
