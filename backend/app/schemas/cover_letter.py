from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class CoverLetterGenerateRequest(BaseModel):
    """Request payload for generating a cover letter draft for an application."""

    tone: Optional[str] = None
    word_limit: Optional[int] = None


class CoverLetterUpdateRequest(BaseModel):
    """Request payload for editing/reviewing a cover letter's content."""

    content: str


class CoverLetterResponse(BaseModel):
    """Response payload representing a cover letter draft."""

    id: UUID
    application_id: UUID
    content: str
    tone: Optional[str]
    word_limit: Optional[int]
    word_count: Optional[int]
    status: str
    warnings: List[str]
    claim_provenance: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
