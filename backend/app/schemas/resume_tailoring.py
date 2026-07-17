from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID

from pydantic import BaseModel, Field


class ResumeTailorRequest(BaseModel):
    """Request payload for tailoring a resume version to a specific job."""

    job_id: UUID


class ClaimProvenance(BaseModel):
    """Links a persisted resume claim back to the profile facts that support it."""

    claim_id: UUID
    claim_text: str
    section: str
    profile_fact_ids: List[UUID] = Field(default_factory=list)


class ResumeTailorResponse(BaseModel):
    """Response payload for a resume tailoring request."""

    resume_version_id: UUID
    requirement_evidence_matrix: List[Dict[str, Any]] = Field(default_factory=list)
    change_log: List[Dict[str, Any]] = Field(default_factory=list)
    claim_provenance: List[ClaimProvenance] = Field(default_factory=list)
    keyword_coverage: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    page_count: int = 1
    quality_score: float = 0.0
