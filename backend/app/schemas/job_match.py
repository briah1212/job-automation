from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class JobMatchScoreBase(BaseModel):
    """Base job match score schema."""
    search_profile_id: UUID
    job_id: UUID
    
    # Match scores (0.0 to 1.0)
    overall_score: float = Field(..., ge=0.0, le=1.0)
    title_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    company_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    location_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    salary_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    skills_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    
    # Match details
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    match_reasoning: Optional[str] = None


class JobMatchScoreCreate(JobMatchScoreBase):
    """Job match score creation schema."""
    pass


class JobMatchScoreUpdate(BaseModel):
    """Job match score update schema."""
    overall_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    title_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    company_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    location_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    salary_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    skills_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    matched_skills: Optional[List[str]] = None
    missing_skills: Optional[List[str]] = None
    match_reasoning: Optional[str] = None


class JobMatchScore(JobMatchScoreBase):
    """Job match score response schema."""
    id: UUID
    user_id: UUID
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
