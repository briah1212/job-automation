from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Profile(Base):
    """User profile with career information.

    EEO/demographic facts (ethnicity, disability, LGBTQ+ identity, gender,
    veteran status) deliberately do NOT live here - per spec section 6,
    "sensitive answers must be stored separately", so those go through
    ReusableAnswer (risk_level="high", user_approved=True) instead, the
    same mechanism a paused application question already writes to.
    """

    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)

    legal_name = Column(String, nullable=True)
    preferred_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    linkedin = Column(String, nullable=True)
    github = Column(String, nullable=True)

    career_interests = Column(Text, nullable=True)
    target_seniority = Column(String, nullable=True)
    work_authorization = Column(String, nullable=True)

    date_of_birth = Column(Date, nullable=True)
    address_line1 = Column(String, nullable=True)
    address_line2 = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    country = Column(String, nullable=True)
    graduation_year = Column(Integer, nullable=True)
    relocation_willingness = Column(String, nullable=True)
    salary_expectation_min = Column(Integer, nullable=True)
    salary_expectation_max = Column(Integer, nullable=True)
    citizenship = Column(String, nullable=True)
    clearance_eligible = Column(Boolean, nullable=True)

    profile_metadata = Column(JSONB, default=dict, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="profile")
