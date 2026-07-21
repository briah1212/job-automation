from __future__ import annotations

import uuid
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.services.field_mapping_service import delete_mapping, list_mappings, update_mapping

router = APIRouter(prefix="/field-mappings", tags=["field-mappings"])


class FieldMappingResponse(BaseModel):
    id: str
    ats_platform: str
    domain: str
    form_fingerprint: str
    field_name: str
    label: Optional[str]
    canonical_name: str
    source: str
    reviewed: bool
    use_count: int

    class Config:
        from_attributes = True


class UpdateFieldMappingRequest(BaseModel):
    canonical_name: str


@router.get("")
def get_field_mappings(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    ats_platform: Annotated[Optional[str], Query()] = None,
    domain: Annotated[Optional[str], Query()] = None,
) -> list[dict[str, Any]]:
    """List learned field mappings, for review - not user-scoped (see FieldMapping's
    docstring), so this is every mapping the system has learned across all runs."""
    mappings = list_mappings(db, ats_platform=ats_platform, domain=domain)
    return [
        {
            "id": str(m.id),
            "ats_platform": m.ats_platform,
            "domain": m.domain,
            "form_fingerprint": m.form_fingerprint,
            "field_name": m.field_name,
            "label": m.label,
            "canonical_name": m.canonical_name,
            "source": m.source,
            "reviewed": m.reviewed,
            "use_count": m.use_count,
        }
        for m in mappings
    ]


@router.patch("/{mapping_id}")
def patch_field_mapping(
    mapping_id: uuid.UUID,
    body: UpdateFieldMappingRequest,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Correct a learned mapping - marks it reviewed, which future auto-learning
    will never silently overwrite."""
    mapping = update_mapping(db, mapping_id, body.canonical_name)
    if mapping is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field mapping not found")
    return {"id": str(mapping.id), "canonical_name": mapping.canonical_name, "reviewed": mapping.reviewed}


@router.delete("/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_field_mapping(
    mapping_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    if not delete_mapping(db, mapping_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field mapping not found")
