from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ApplicationReviewResultBase(BaseModel):
    """Base application review result schema.

    Named ApplicationReviewResult (rather than ApplicationReview) to avoid colliding
    with the existing app.schemas.application.ApplicationReview, which represents a
    human approval action rather than an automated compliance review record.
    """
    passed: bool
    blocking_findings: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float
    recommended_correction: Optional[str] = None


class ApplicationReviewResultCreate(ApplicationReviewResultBase):
    """Application review result creation schema."""
    application_id: UUID


class ApplicationReviewResult(ApplicationReviewResultBase):
    """Application review result response schema."""
    id: UUID
    application_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}
