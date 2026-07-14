from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class JobMatchScore(Base):
    """Job match score model linking jobs to search profiles."""
    
    __tablename__ = "job_match_scores"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    search_profile_id = Column(UUID(as_uuid=True), ForeignKey("search_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("canonical_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Match scores (0.0 to 1.0)
    overall_score = Column(Float, nullable=False, index=True)
    title_score = Column(Float, nullable=True)
    company_score = Column(Float, nullable=True)
    location_score = Column(Float, nullable=True)
    salary_score = Column(Float, nullable=True)
    skills_score = Column(Float, nullable=True)
    
    # Match details
    matched_skills = Column(JSONB, default=list, nullable=False)
    missing_skills = Column(JSONB, default=list, nullable=False)
    match_reasoning = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="job_match_scores")
    search_profile = relationship("SearchProfile", back_populates="job_matches")
    job = relationship("CanonicalJob", back_populates="match_scores")
