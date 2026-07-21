from __future__ import annotations

from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import RequireInternalApiKey
from app.core.database import get_db
from app.services.field_mapping_service import get_mappings_for_form, record_mapping

router = APIRouter(
    prefix="/internal/field-mappings",
    tags=["internal"],
    dependencies=[RequireInternalApiKey],
)


class LookupRequest(BaseModel):
    ats_platform: str
    domain: str
    form_fingerprint: str


class RecordRequest(BaseModel):
    ats_platform: str
    domain: str
    form_fingerprint: str
    field_name: str
    label: Optional[str] = None
    canonical_name: str
    source: str = "learned"


@router.post("/lookup")
def lookup(body: LookupRequest, db: Annotated[Session, Depends(get_db)]) -> Dict[str, str]:
    """Return {field_name: canonical_name} for a form shape already learned."""
    return get_mappings_for_form(db, body.ats_platform, body.domain, body.form_fingerprint)


@router.post("/record")
def record(body: RecordRequest, db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    """Persist (or bump the use count of) a mapping, learned once, reused forever."""
    mapping = record_mapping(
        db=db,
        ats_platform=body.ats_platform,
        domain=body.domain,
        form_fingerprint=body.form_fingerprint,
        field_name=body.field_name,
        label=body.label,
        canonical_name=body.canonical_name,
        source=body.source,
    )
    return {"id": str(mapping.id), "use_count": mapping.use_count}
