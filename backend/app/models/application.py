from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class ApplicationStatus(str, enum.Enum):
    """Application status enumeration."""
    draft = "draft"
    ready = "ready"
    submitted = "submitted"
    in_review = "in_review"
    rejected = "rejected"
    archived = "archived"


class ApplicationPipelineStatus(str, enum.Enum):
    """Application pipeline status enumeration."""
    not_started = "not_started"
    draft = "draft"
    awaiting_review = "awaiting_review"
    approved = "approved"
    browser_running = "browser_running"
    paused = "paused"
    submitted = "submitted"
    confirmed = "confirmed"
    failed_retryable = "failed_retryable"
    failed_terminal = "failed_terminal"


class Application(Base):
    """Job application model."""
    
    __tablename__ = "applications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("canonical_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_version_id = Column(UUID(as_uuid=True), ForeignKey("resume_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    
    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.draft, nullable=False, index=True)
    pipeline_status = Column(Enum(ApplicationPipelineStatus), default=ApplicationPipelineStatus.not_started, nullable=False, index=True)
    
    answers = Column(JSONB, default=dict, nullable=False)
    review_result = Column(JSONB, default=dict, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="applications")
    job = relationship("CanonicalJob", back_populates="applications")
    resume_version = relationship("ResumeVersion", back_populates="applications")
