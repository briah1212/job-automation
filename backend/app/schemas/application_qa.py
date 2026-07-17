from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel

from app.schemas.reusable_answer import ReusableAnswerCreate as ReusableAnswerCreateRequest
from app.schemas.reusable_answer import ReusableAnswer as ReusableAnswerResponse

__all__ = [
    "GenerateQuestionsRequest",
    "QuestionWithAnswer",
    "UpdateAnswerRequest",
    "ReusableAnswerCreateRequest",
    "ReusableAnswerResponse",
]


class GenerateQuestionsRequest(BaseModel):
    """Request to generate application questions and answers.

    If question_texts is omitted, questions are derived from the job's extracted_data
    (or a hardcoded default set as a fallback).
    """
    question_texts: Optional[List[str]] = None


class QuestionWithAnswer(BaseModel):
    """An application question joined with its current answer, if any."""
    id: UUID
    question_text: str
    question_type: str
    risk_level: str
    answer: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class UpdateAnswerRequest(BaseModel):
    """Request body for manually updating an application answer."""
    answer_text: str
