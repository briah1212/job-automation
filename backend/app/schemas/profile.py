from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


class ProfileBase(BaseModel):
    """Base profile schema."""
    legal_name: Optional[str] = None
    preferred_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    career_interests: Optional[str] = None
    target_seniority: Optional[str] = None
    work_authorization: Optional[str] = None

    # Logistics facts (spec section 6, "Personal Contact Information" /
    # "Professional Summary Facts") - EEO/demographic facts (ethnicity,
    # disability, LGBTQ+ identity, gender, veteran status) deliberately
    # live in ReusableAnswer instead, not here; see app/models/profile.py.
    date_of_birth: Optional[date] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    graduation_year: Optional[int] = None
    relocation_willingness: Optional[str] = None
    salary_expectation_min: Optional[int] = None
    salary_expectation_max: Optional[int] = None
    citizenship: Optional[str] = None
    clearance_eligible: Optional[bool] = None


class ProfileCreate(ProfileBase):
    """Profile creation schema."""
    pass


class ProfileUpdate(ProfileBase):
    """Profile update schema."""
    pass


class Profile(ProfileBase):
    """Profile response schema."""
    id: UUID
    user_id: UUID
    profile_metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}
