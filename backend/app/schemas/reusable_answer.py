from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ReusableAnswerBase(BaseModel):
    """Base reusable answer schema."""
    canonical_question: str
    semantic_variants: List[str] = Field(default_factory=list)

    exact_answer: str
    allowed_paraphrasing: bool = False
    risk_level: str
    categories: List[str] = Field(default_factory=list)

    expiration_date: Optional[datetime] = None
    user_approved: bool = False


class ReusableAnswerCreate(ReusableAnswerBase):
    """Reusable answer creation schema."""
    pass


class ReusableAnswer(ReusableAnswerBase):
    """Reusable answer response schema."""
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
