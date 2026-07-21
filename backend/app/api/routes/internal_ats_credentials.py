from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import RequireInternalApiKey
from app.core.credential_cipher import CredentialCipher, get_credential_cipher
from app.core.database import get_db
from app.models import AtsCredentialStatus
from app.services.ats_credential_vault import get_or_create_credential, mark_credential_status

router = APIRouter(
    prefix="/internal/ats-credentials",
    tags=["internal"],
    dependencies=[RequireInternalApiKey],
)


class GetOrCreateCredentialRequest(BaseModel):
    user_id: uuid.UUID
    ats_platform: str
    tenant_key: str
    email: str


class MarkStatusRequest(BaseModel):
    status: str


@router.post("/get-or-create")
def get_or_create(
    body: GetOrCreateCredentialRequest,
    db: Annotated[Session, Depends(get_db)],
    cipher: Annotated[CredentialCipher, Depends(get_credential_cipher)],
) -> dict[str, Any]:
    """Return the stored credential for (user, platform, tenant), creating one if none exists.

    Called only by browser-worker over the internal network, never by the
    public frontend - see require_internal_api_key. This is the one place in
    the system a plaintext ATS account password is ever transmitted, and it
    happens only over this one call, for this one tenant.
    """
    return get_or_create_credential(
        db=db,
        cipher=cipher,
        user_id=body.user_id,
        ats_platform=body.ats_platform,
        tenant_key=body.tenant_key,
        email=body.email,
    )


@router.post("/{credential_id}/mark-status")
def mark_status(
    credential_id: uuid.UUID,
    body: MarkStatusRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Update a credential's lifecycle status, e.g. login_failed after a failed login attempt."""
    try:
        new_status = AtsCredentialStatus(body.status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status: {body.status!r}. Must be one of {[s.value for s in AtsCredentialStatus]}",
        )

    updated = mark_credential_status(db, credential_id, new_status)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")

    return {"credential_id": str(credential_id), "status": new_status.value}
