from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class ResumeStatus(str, enum.Enum):
    """Resume status enumeration."""
    draft = "draft"
    parsing = "parsing"
    parsed = "parsed"
    tailoring = "tailoring"
    ready = "ready"
    approved = "approved"
    archived = "archived"


class ResumeFamily(Base):
    """Resume family grouping related versions."""
    
    __tablename__ = "resume_families"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    name = Column(String, nullable=False)
    target_category = Column(String, nullable=True)
    status = Column(Enum(ResumeStatus), default=ResumeStatus.draft, nullable=False, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="resume_families")
    versions = relationship("ResumeVersion", back_populates="family")


class ResumeVersion(Base):
    """Individual resume version."""
    
    __tablename__ = "resume_versions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("resume_families.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("resume_versions.id", ondelete="SET NULL"), nullable=True)
    
    version = Column(Integer, nullable=False)
    status = Column(Enum(ResumeStatus), default=ResumeStatus.draft, nullable=False, index=True)
    
    file_path = Column(String, nullable=True)
    file_hash = Column(String, nullable=True)
    parsed_data = Column(JSONB, default=dict, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    family = relationship("ResumeFamily", back_populates="versions")
    parent = relationship("ResumeVersion", remote_side=[id], backref="children")
    applications = relationship("Application", back_populates="resume_version")
