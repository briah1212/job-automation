from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class ResumeClaim(Base):
    """A single factual claim made within a rendered resume version."""

    __tablename__ = "resume_claims"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_version_id = Column(UUID(as_uuid=True), ForeignKey("resume_versions.id", ondelete="CASCADE"), nullable=False, index=True)

    section = Column(String, nullable=False)
    claim_text = Column(Text, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    resume_version = relationship("ResumeVersion", back_populates="claims")
    sources = relationship("ResumeClaimSource", back_populates="resume_claim", cascade="all, delete-orphan")


class ResumeClaimSource(Base):
    """Links a resume claim back to the profile fact(s) that support it."""

    __tablename__ = "resume_claim_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_claim_id = Column(UUID(as_uuid=True), ForeignKey("resume_claims.id", ondelete="CASCADE"), nullable=False, index=True)
    profile_fact_id = Column(UUID(as_uuid=True), ForeignKey("profile_facts.id", ondelete="SET NULL"), nullable=True, index=True)

    strength = Column(Float, nullable=False)
    explanation = Column(Text, nullable=True)

    # Relationships
    resume_claim = relationship("ResumeClaim", back_populates="sources")
    profile_fact = relationship("ProfileFact")
