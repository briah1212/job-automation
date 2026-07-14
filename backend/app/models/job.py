from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class JobStatus(str, enum.Enum):
    """Job status enumeration."""
    discovered = "discovered"
    extracting = "extracting"
    scored = "scored"
    saved = "saved"
    shortlisted = "shortlisted"
    preparing = "preparing"
    ready_for_review = "ready_for_review"
    approved = "approved"
    rejected_by_rule = "rejected_by_rule"
    archived = "archived"


class CanonicalJob(Base):
    """Canonical job posting model."""
    
    __tablename__ = "canonical_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    company = Column(String, nullable=False)
    title = Column(String, nullable=False)
    location = Column(String, nullable=True)
    remote_policy = Column(String, nullable=True)
    
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    
    description = Column(Text, nullable=True)
    extracted_data = Column(JSONB, default=dict, nullable=False)
    
    status = Column(Enum(JobStatus), default=JobStatus.discovered, nullable=False, index=True)
    score = Column(Float, nullable=True, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="jobs")
    applications = relationship("Application", back_populates="job")
    match_scores = relationship("JobMatchScore", back_populates="job", cascade="all, delete-orphan")
