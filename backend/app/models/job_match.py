from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class JobMatchScore(Base):
    """Job match score model for matching jobs to users."""
    
    __tablename__ = "job_match_scores"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("canonical_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Overall score (0-100)
    overall_score = Column(Integer, nullable=False, index=True)
    
    # Dimensional scores (0.0 to 1.0)
    skill_score = Column(Float, nullable=False)
    experience_score = Column(Float, nullable=False)
    seniority_score = Column(Float, nullable=False)
    location_score = Column(Float, nullable=False)
    salary_score = Column(Float, nullable=False)
    
    # Match analysis
    hard_blockers = Column(JSONB, default=list, nullable=False)
    strong_matches = Column(JSONB, default=list, nullable=False)
    soft_gaps = Column(JSONB, default=list, nullable=False)
    missing_info = Column(JSONB, default=list, nullable=False)
    
    # Recommendation
    recommended_action = Column(String, nullable=False)
    explanation = Column(Text, nullable=True)
    
    # Resume selection
    matched_resume_id = Column(UUID(as_uuid=True), ForeignKey("resume_versions.id", ondelete="SET NULL"), nullable=True)
    resume_selection_rationale = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="job_match_scores")
    job = relationship("CanonicalJob", back_populates="match_scores")
    matched_resume = relationship("ResumeVersion")
