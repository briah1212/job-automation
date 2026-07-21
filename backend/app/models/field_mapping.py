from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class FieldMapping(Base):
    """A durable, reviewable field-name/label -> canonical-name mapping,
    scoped to a specific form shape (see spec.md section 14.3: "Store learned
    mappings by: Domain, ATS, Form fingerprint, Label pattern").

    Not user-scoped deliberately - a form's field structure on a given site is
    the same for everyone who applies there, so a mapping learned once is
    reused for every future application against that exact form shape,
    matching "learned once and reused forever."
    """

    __tablename__ = "field_mappings"
    __table_args__ = (
        UniqueConstraint("ats_platform", "domain", "form_fingerprint", "field_name", name="uq_field_mappings_form_field"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    ats_platform = Column(String, nullable=False, index=True)
    domain = Column(String, nullable=False, index=True)
    form_fingerprint = Column(String, nullable=False, index=True)

    field_name = Column(String, nullable=False)
    label = Column(Text, nullable=True)
    canonical_name = Column(String, nullable=False)

    source = Column(String, nullable=False)  # "learned" (auto, from a regex match) | "reviewed" (human-confirmed/edited)
    reviewed = Column(Boolean, default=False, nullable=False)
    use_count = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
