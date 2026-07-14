from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SearchProfileBase(BaseModel):
    """Base search profile schema."""
    name: str
    enabled: bool = True
    
    # Career categories and titles
    career_categories: List[str] = Field(default_factory=list)
    include_titles: List[str] = Field(default_factory=list)
    exclude_titles: List[str] = Field(default_factory=list)
    
    # Skills
    include_skills: List[str] = Field(default_factory=list)
    exclude_skills: List[str] = Field(default_factory=list)
    
    # Location and remote
    locations: List[str] = Field(default_factory=list)
    remote_policy: Optional[str] = None
    
    # Salary
    min_salary: Optional[int] = None
    
    # Employment and seniority
    employment_types: List[str] = Field(default_factory=list)
    seniority_levels: List[str] = Field(default_factory=list)
    
    # Companies
    companies: List[str] = Field(default_factory=list)
    excluded_companies: List[str] = Field(default_factory=list)


class SearchProfileCreate(SearchProfileBase):
    """Search profile creation schema."""
    pass


class SearchProfileUpdate(BaseModel):
    """Search profile update schema."""
    name: Optional[str] = None
    enabled: Optional[bool] = None
    
    # Career categories and titles
    career_categories: Optional[List[str]] = None
    include_titles: Optional[List[str]] = None
    exclude_titles: Optional[List[str]] = None
    
    # Skills
    include_skills: Optional[List[str]] = None
    exclude_skills: Optional[List[str]] = None
    
    # Location and remote
    locations: Optional[List[str]] = None
    remote_policy: Optional[str] = None
    
    # Salary
    min_salary: Optional[int] = None
    
    # Employment and seniority
    employment_types: Optional[List[str]] = None
    seniority_levels: Optional[List[str]] = None
    
    # Companies
    companies: Optional[List[str]] = None
    excluded_companies: Optional[List[str]] = None


class SearchProfile(SearchProfileBase):
    """Search profile response schema."""
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}
