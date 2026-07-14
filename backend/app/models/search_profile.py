from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class SearchProfile(Base):
    """Search profile model for job search criteria."""
    
    __tablename__ = "search_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Profile metadata
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Search criteria
    desired_titles = Column(JSONB, default=list, nullable=False)  # List of job titles
    desired_companies = Column(JSONB, default=list, nullable=False)  # List of companies
    desired_locations = Column(JSONB, default=list, nullable=False)  # List of locations
    remote_preference = Column(String(50), nullable=True)  # e.g., 'remote', 'hybrid', 'onsite'
    
    # Salary expectations
    min_salary = Column(Integer, nullable=True)
    max_salary = Column(Integer, nullable=True)
    
    # Skills and requirements
    required_skills = Column(JSONB, default=list, nullable=False)
    preferred_skills = Column(JSONB, default=list, nullable=False)
    excluded_keywords = Column(JSONB, default=list, nullable=False)
    
    # Scoring weights (for matching algorithm)
    title_weight = Column(Float, default=1.0, nullable=False)
    company_weight = Column(Float, default=0.8, nullable=False)
    location_weight = Column(Float, default=0.7, nullable=False)
    salary_weight = Column(Float, default=0.9, nullable=False)
    skills_weight = Column(Float, default=1.0, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="search_profiles")
    job_matches = relationship("JobMatchScore", back_populates="search_profile", cascade="all, delete-orphan")
