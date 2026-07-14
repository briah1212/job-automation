from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.job import JobStatus


class JobBase(BaseModel):
    """Base job schema."""
    company: str
    title: str
    location: Optional[str] = None
    remote_policy: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    description: Optional[str] = None


class JobCreate(JobBase):
    """Job creation schema."""
    pass


class JobImportUrl(BaseModel):
    """Job import from URL schema."""
    url: str


class JobScore(BaseModel):
    """Job scoring schema."""
    score: float


class Job(JobBase):
    """Job response schema."""
    id: UUID
    user_id: UUID
    status: JobStatus
    score: Optional[float]
    extracted_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}
