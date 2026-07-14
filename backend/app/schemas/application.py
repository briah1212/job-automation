from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.application import ApplicationPipelineStatus, ApplicationStatus


class ApplicationBase(BaseModel):
    """Base application schema."""
    job_id: UUID
    resume_version_id: Optional[UUID] = None


class ApplicationCreate(ApplicationBase):
    """Application creation schema."""
    pass


class ApplicationReview(BaseModel):
    """Application review schema."""
    approved: bool
    comments: Optional[str] = None


class ApplicationApprove(BaseModel):
    """Application approval schema."""
    approved: bool


class Application(ApplicationBase):
    """Application response schema."""
    id: UUID
    user_id: UUID
    status: ApplicationStatus
    pipeline_status: ApplicationPipelineStatus
    answers: Dict[str, Any]
    review_result: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}
