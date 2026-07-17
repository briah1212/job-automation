from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ResumeClaimBase(BaseModel):
    """Base resume claim schema."""
    section: str
    claim_text: str


class ResumeClaimCreate(ResumeClaimBase):
    """Resume claim creation schema."""
    resume_version_id: UUID


class ResumeClaim(ResumeClaimBase):
    """Resume claim response schema."""
    id: UUID
    resume_version_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class ResumeClaimSourceBase(BaseModel):
    """Base resume claim source schema."""
    strength: float
    explanation: Optional[str] = None


class ResumeClaimSourceCreate(ResumeClaimSourceBase):
    """Resume claim source creation schema."""
    resume_claim_id: UUID
    profile_fact_id: Optional[UUID] = None


class ResumeClaimSource(ResumeClaimSourceBase):
    """Resume claim source response schema."""
    id: UUID
    resume_claim_id: UUID
    profile_fact_id: Optional[UUID]

    model_config = {"from_attributes": True}
