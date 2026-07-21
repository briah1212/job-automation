from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import FieldMapping


def get_mappings_for_form(db: Session, ats_platform: str, domain: str, form_fingerprint: str) -> Dict[str, str]:
    """Return {field_name: canonical_name} for every mapping already learned
    (or reviewed) for this exact form shape."""
    rows = (
        db.query(FieldMapping)
        .filter(
            FieldMapping.ats_platform == ats_platform,
            FieldMapping.domain == domain,
            FieldMapping.form_fingerprint == form_fingerprint,
        )
        .all()
    )
    return {row.field_name: row.canonical_name for row in rows}


def record_mapping(
    db: Session,
    ats_platform: str,
    domain: str,
    form_fingerprint: str,
    field_name: str,
    label: Optional[str],
    canonical_name: str,
    source: str = "learned",
) -> FieldMapping:
    """Upsert a mapping and bump its use count - idempotent, safe to call on
    every successful fill so "used" mappings stay distinguishable from
    never-exercised guesses without a separate tracking table."""
    existing = (
        db.query(FieldMapping)
        .filter(
            FieldMapping.ats_platform == ats_platform,
            FieldMapping.domain == domain,
            FieldMapping.form_fingerprint == form_fingerprint,
            FieldMapping.field_name == field_name,
        )
        .first()
    )
    if existing is not None:
        existing.use_count += 1
        existing.last_used_at = datetime.utcnow()
        db.commit()
        return existing

    mapping = FieldMapping(
        ats_platform=ats_platform,
        domain=domain,
        form_fingerprint=form_fingerprint,
        field_name=field_name,
        label=label,
        canonical_name=canonical_name,
        source=source,
        use_count=1,
        last_used_at=datetime.utcnow(),
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


def list_mappings(db: Session, ats_platform: Optional[str] = None, domain: Optional[str] = None) -> List[FieldMapping]:
    query = db.query(FieldMapping)
    if ats_platform:
        query = query.filter(FieldMapping.ats_platform == ats_platform)
    if domain:
        query = query.filter(FieldMapping.domain == domain)
    return query.order_by(FieldMapping.updated_at.desc()).all()


def update_mapping(db: Session, mapping_id: uuid.UUID, canonical_name: str) -> Optional[FieldMapping]:
    """A human correcting a learned mapping - marks it reviewed/source=reviewed
    so it's visibly distinct from an unreviewed auto-learned guess, and takes
    priority over any future auto-learn attempt for the same field (record_mapping
    treats an existing row as authoritative and only bumps use_count, never
    silently overwrites canonical_name)."""
    mapping = db.query(FieldMapping).filter(FieldMapping.id == mapping_id).first()
    if mapping is None:
        return None
    mapping.canonical_name = canonical_name
    mapping.source = "reviewed"
    mapping.reviewed = True
    db.commit()
    db.refresh(mapping)
    return mapping


def delete_mapping(db: Session, mapping_id: uuid.UUID) -> bool:
    mapping = db.query(FieldMapping).filter(FieldMapping.id == mapping_id).first()
    if mapping is None:
        return False
    db.delete(mapping)
    db.commit()
    return True
