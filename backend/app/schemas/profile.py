from __future__ import annotations

from datetime import datetime
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
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}
