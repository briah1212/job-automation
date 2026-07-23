from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.resume import ResumeStatus


class ResumeFamilyBase(BaseModel):
    """Base resume family schema."""
    name: str
    target_category: Optional[str] = None


class ResumeFamilyCreate(ResumeFamilyBase):
    """Resume family creation schema."""
    pass


class ResumeFamily(ResumeFamilyBase):
    """Resume family response schema."""
    id: UUID
    user_id: UUID
    status: ResumeStatus
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class ResumeVersionBase(BaseModel):
    """Base resume version schema."""
    version: int


class ResumeVersionCreate(ResumeVersionBase):
    """Resume version creation schema."""
    family_id: UUID
    parent_id: Optional[UUID] = None
    file_path: Optional[str] = None


class ResumeVersion(ResumeVersionBase):
    """Resume version response schema."""
    id: UUID
    family_id: UUID
    parent_id: Optional[UUID]
    status: ResumeStatus
    file_path: Optional[str]
    file_hash: Optional[str]
    parsed_data: Dict[str, Any]
    family_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class ResumeUpload(BaseModel):
    """Resume upload response schema."""
    family: ResumeFamily
    version: ResumeVersion
