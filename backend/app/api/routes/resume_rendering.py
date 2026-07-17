from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models import DocumentLock, DocumentRendering, ResumeFamily, ResumeVersion
from app.schemas.document_lock import DocumentLock as DocumentLockSchema
from app.schemas.document_lock import DocumentLockCreate
from app.schemas.document_rendering import DocumentRendering as DocumentRenderingSchema
from app.services.resume_diff import compute_resume_diff
from app.services.resume_rendering import render_resume_pdf

router = APIRouter(prefix="/resumes", tags=["resume-rendering"])


class RenderRequest(BaseModel):
    format: str


def _get_owned_version(
    resume_version_id: uuid.UUID, current_user, db: Session
) -> tuple[ResumeVersion, ResumeFamily]:
    """Load a resume version + its family, ensuring it belongs to current_user."""
    result = (
        db.query(ResumeVersion, ResumeFamily)
        .join(ResumeFamily, ResumeVersion.family_id == ResumeFamily.id)
        .filter(
            ResumeVersion.id == resume_version_id,
            ResumeFamily.user_id == current_user.id,
        )
        .first()
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume version not found"
        )
    return result


def _get_owned_family(family_id: uuid.UUID, current_user, db: Session) -> ResumeFamily:
    family = (
        db.query(ResumeFamily)
        .filter(ResumeFamily.id == family_id, ResumeFamily.user_id == current_user.id)
        .first()
    )
    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume family not found"
        )
    return family


def _storage_base_dir() -> str:
    """Resolve the local `storage/` directory backend/storage."""
    import os

    # backend/app/api/routes/resume_rendering.py -> backend/
    backend_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    return os.path.join(backend_root, "storage")


@router.post(
    "/{resume_version_id}/render",
    response_model=DocumentRenderingSchema,
    status_code=status.HTTP_201_CREATED,
)
def render_resume(
    resume_version_id: uuid.UUID,
    body: RenderRequest,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> DocumentRendering:
    """Render a resume version to PDF (or DOCX, not yet implemented)."""
    if body.format not in ("pdf", "docx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="format must be one of: pdf, docx",
        )

    if body.format == "docx":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="DOCX rendering not yet implemented",
        )

    version, family = _get_owned_version(resume_version_id, current_user, db)

    relative_path = f"resumes/{family.user_id}/{family.id}/rendered/{version.id}.pdf"
    absolute_path = f"{_storage_base_dir()}/{relative_path}"

    page_count = render_resume_pdf(version, absolute_path)

    rendering = DocumentRendering(
        resume_version_id=version.id,
        format="pdf",
        file_path=relative_path,
        page_count=page_count,
    )
    db.add(rendering)
    db.commit()
    db.refresh(rendering)
    return rendering


@router.get("/{resume_version_id}/diff", response_model=None)
def diff_resume(
    resume_version_id: uuid.UUID,
    base_version_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Compute a human-reviewable diff between two resume versions."""
    new_version, _ = _get_owned_version(resume_version_id, current_user, db)
    base_version, _ = _get_owned_version(base_version_id, current_user, db)

    return compute_resume_diff(base_version, new_version)


@router.post(
    "/families/{family_id}/locks",
    response_model=DocumentLockSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_lock(
    family_id: uuid.UUID,
    body: DocumentLockCreate,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> DocumentLock:
    """Create a field lock for a resume family."""
    _get_owned_family(family_id, current_user, db)

    lock = DocumentLock(
        resume_family_id=family_id,
        lock_type=body.lock_type,
        target_ref=body.target_ref,
        value=body.value,
    )
    db.add(lock)
    db.commit()
    db.refresh(lock)
    return lock


@router.get("/families/{family_id}/locks", response_model=list[DocumentLockSchema])
def list_locks(
    family_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> list[DocumentLock]:
    """List all field locks for a resume family."""
    _get_owned_family(family_id, current_user, db)

    return (
        db.query(DocumentLock)
        .filter(DocumentLock.resume_family_id == family_id)
        .order_by(DocumentLock.created_at.desc())
        .all()
    )
