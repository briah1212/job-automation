from __future__ import annotations

import hashlib
import os
import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models import ResumeFamily, ResumeStatus, ResumeVersion
from app.schemas import ResumeUpload
from app.schemas.resume import ResumeFamily as ResumeFamilySchema
from app.schemas.resume import ResumeVersion as ResumeVersionSchema

router = APIRouter(prefix="/resumes", tags=["resumes"])

# Matches queue_worker.py's _STORAGE_ROOT - both api and browser-worker mount
# the same ./storage host directory at this path (see docker-compose.yml), so
# a file written here by this endpoint is exactly what BrowserWorker reads
# when it uploads a resume during a real ATS submission.
_STORAGE_ROOT = "/app/storage"

# The filename becomes part of a filesystem write path below (it previously
# only lived in a DB column), so strip anything that isn't a safe filename
# character to rule out path traversal via a crafted upload filename.
_UNSAFE_FILENAME_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]")


def _safe_filename(filename: str | None) -> str:
    name = os.path.basename(filename or "resume")
    name = _UNSAFE_FILENAME_CHARS_RE.sub("_", name)
    return name or "resume"


@router.get("", response_model=list[ResumeFamilySchema])
def list_resumes(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)]
) -> list[ResumeFamily]:
    """List all resume families for current user."""
    families = db.query(ResumeFamily).filter(
        ResumeFamily.user_id == current_user.id
    ).order_by(ResumeFamily.created_at.desc()).all()
    return families


@router.get("/versions", response_model=list[ResumeVersionSchema])
def list_resume_versions(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)]
) -> list[ResumeVersion]:
    """List all resume versions for current user, across all families."""
    versions = (
        db.query(ResumeVersion)
        .join(ResumeFamily, ResumeVersion.family_id == ResumeFamily.id)
        .filter(ResumeFamily.user_id == current_user.id)
        .order_by(ResumeVersion.created_at.desc())
        .all()
    )
    return versions


@router.post("", response_model=ResumeUpload, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    current_user: CurrentUser,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
) -> dict:
    """Upload a new resume."""
    # Read file content
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()

    # Create resume family
    family = ResumeFamily(
        user_id=current_user.id,
        name=file.filename or "Untitled Resume",
        status=ResumeStatus.parsing
    )
    db.add(family)
    db.flush()

    # Create version
    relative_path = f"resumes/{current_user.id}/{family.id}/v1_{_safe_filename(file.filename)}"
    version = ResumeVersion(
        family_id=family.id,
        version=1,
        status=ResumeStatus.parsing,
        file_path=relative_path,
        file_hash=file_hash
    )
    db.add(version)

    absolute_path = os.path.join(_STORAGE_ROOT, relative_path)
    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
    with open(absolute_path, "wb") as f:
        f.write(content)

    db.commit()
    db.refresh(family)
    db.refresh(version)

    # TODO: trigger a real parsing workflow (structured extraction of resume
    # content) - status stays "parsing" until that exists; out of scope for
    # browser-automation validation, which only needs the file on disk.

    return {"family": family, "version": version}


@router.post("/{resume_id}/approve", response_model=ResumeFamilySchema)
def approve_resume(
    resume_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)]
) -> ResumeFamily:
    """Approve a resume for use."""
    family = db.query(ResumeFamily).filter(
        ResumeFamily.id == resume_id,
        ResumeFamily.user_id == current_user.id
    ).first()
    
    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )
    
    family.status = ResumeStatus.approved
    db.commit()
    db.refresh(family)
    return family
