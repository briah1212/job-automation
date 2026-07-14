from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base


class WorkflowStatus(str, enum.Enum):
    """Workflow status enumeration."""
    pending = "pending"
    running = "running"
    waiting_user_input = "waiting_user_input"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class WorkflowTask(Base):
    """Workflow task tracking."""
    
    __tablename__ = "workflow_tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    workflow_type = Column(String, nullable=False, index=True)
    entity_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    status = Column(Enum(WorkflowStatus), default=WorkflowStatus.pending, nullable=False, index=True)
    current_step = Column(String, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    error = Column(Text, nullable=True)
    
    task_metadata = Column(JSONB, default=dict, nullable=False)
    
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
