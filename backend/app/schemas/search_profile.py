from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SearchProfileBase(BaseModel):
    """Base search profile schema."""
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    is_active: bool = True
    
    # Search criteria
    desired_titles: List[str] = Field(default_factory=list)
    desired_companies: List[str] = Field(default_factory=list)
    desired_locations: List[str] = Field(default_factory=list)
    remote_preference: Optional[str] = Field(None, max_length=50)
    
    # Salary expectations
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    
    # Skills and requirements
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    excluded_keywords: List[str] = Field(default_factory=list)
    
    # Scoring weights
    title_weight: float = Field(default=1.0, ge=0.0, le=2.0)
    company_weight: float = Field(default=0.8, ge=0.0, le=2.0)
    location_weight: float = Field(default=0.7, ge=0.0, le=2.0)
    salary_weight: float = Field(default=0.9, ge=0.0, le=2.0)
    skills_weight: float = Field(default=1.0, ge=0.0, le=2.0)


class SearchProfileCreate(SearchProfileBase):
    """Search profile creation schema."""
    pass


class SearchProfileUpdate(BaseModel):
    """Search profile update schema."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    
    # Search criteria
    desired_titles: Optional[List[str]] = None
    desired_companies: Optional[List[str]] = None
    desired_locations: Optional[List[str]] = None
    remote_preference: Optional[str] = Field(None, max_length=50)
    
    # Salary expectations
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    
    # Skills and requirements
    required_skills: Optional[List[str]] = None
    preferred_skills: Optional[List[str]] = None
    excluded_keywords: Optional[List[str]] = None
    
    # Scoring weights
    title_weight: Optional[float] = Field(None, ge=0.0, le=2.0)
    company_weight: Optional[float] = Field(None, ge=0.0, le=2.0)
    location_weight: Optional[float] = Field(None, ge=0.0, le=2.0)
    salary_weight: Optional[float] = Field(None, ge=0.0, le=2.0)
    skills_weight: Optional[float] = Field(None, ge=0.0, le=2.0)


class SearchProfile(SearchProfileBase):
    """Search profile response schema."""
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}
