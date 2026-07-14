from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.workflow import WorkflowStatus


class WorkflowTaskBase(BaseModel):
    """Base workflow task schema."""
    workflow_type: str
    entity_id: Optional[UUID] = None


class WorkflowTaskCreate(WorkflowTaskBase):
    """Workflow task creation schema."""
    pass


class WorkflowTask(WorkflowTaskBase):
    """Workflow task response schema."""
    id: UUID
    status: WorkflowStatus
    current_step: Optional[str]
    retry_count: int
    error: Optional[str]
    metadata: Dict[str, Any]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}
