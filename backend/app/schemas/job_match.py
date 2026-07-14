from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class JobMatchScoreBase(BaseModel):
    """Base job match score schema."""
    job_id: UUID
    
    # Overall score (0-100)
    overall_score: int = Field(..., ge=0, le=100)
    
    # Dimensional scores (0-100)
    skill_score: float = Field(..., ge=0.0, le=100.0)
    experience_score: float = Field(..., ge=0.0, le=100.0)
    seniority_score: float = Field(..., ge=0.0, le=100.0)
    location_score: float = Field(..., ge=0.0, le=100.0)
    salary_score: float = Field(..., ge=0.0, le=100.0)
    
    # Match analysis
    hard_blockers: List[Dict[str, Any]] = Field(default_factory=list)
    strong_matches: List[Dict[str, Any]] = Field(default_factory=list)
    soft_gaps: List[Dict[str, Any]] = Field(default_factory=list)
    missing_info: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Recommendation
    recommended_action: str
    explanation: Optional[str] = None


class JobMatchScoreCreate(JobMatchScoreBase):
    """Job match score creation schema."""
    pass


class JobMatchScoreUpdate(BaseModel):
    """Job match score update schema."""
    overall_score: Optional[int] = Field(None, ge=0, le=100)
    skill_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    experience_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    seniority_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    location_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    salary_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    hard_blockers: Optional[List[Dict[str, Any]]] = None
    strong_matches: Optional[List[Dict[str, Any]]] = None
    soft_gaps: Optional[List[Dict[str, Any]]] = None
    missing_info: Optional[List[Dict[str, Any]]] = None
    recommended_action: Optional[str] = None
    explanation: Optional[str] = None


class JobMatchScore(JobMatchScoreBase):
    """Job match score response schema."""
    id: UUID
    user_id: UUID
    matched_resume_id: Optional[UUID] = None
    resume_selection_rationale: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class ResumeSelectionResult(BaseModel):
    """Schema for resume selection recommendation result."""
    job_id: UUID
    recommended_resume_id: UUID
    match_score: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    customization_suggestions: List[str] = Field(default_factory=list)
    
    model_config = {"from_attributes": True}
