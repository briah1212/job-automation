from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class SearchProfile(Base):
    """Search profile model for job search criteria."""
    
    __tablename__ = "search_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Profile metadata
    name = Column(String, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False, index=True)
    
    # Search criteria - career categories and titles
    career_categories = Column(ARRAY(String), default=list, nullable=False)
    include_titles = Column(ARRAY(String), default=list, nullable=False)
    exclude_titles = Column(ARRAY(String), default=list, nullable=False)
    
    # Skills
    include_skills = Column(ARRAY(String), default=list, nullable=False)
    exclude_skills = Column(ARRAY(String), default=list, nullable=False)
    
    # Location and remote
    locations = Column(ARRAY(String), default=list, nullable=False)
    remote_policy = Column(String, nullable=True)
    
    # Salary
    min_salary = Column(Integer, nullable=True)
    
    # Employment and seniority
    employment_types = Column(ARRAY(String), default=list, nullable=False)
    seniority_levels = Column(ARRAY(String), default=list, nullable=False)
    
    # Companies
    companies = Column(ARRAY(String), default=list, nullable=False)
    excluded_companies = Column(ARRAY(String), default=list, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="search_profiles")
