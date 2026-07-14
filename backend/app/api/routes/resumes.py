from __future__ import annotations

import hashlib
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models import ResumeFamily, ResumeStatus, ResumeVersion
from app.schemas import ResumeUpload
from app.schemas.resume import ResumeFamily as ResumeFamilySchema

router = APIRouter(prefix="/resumes", tags=["resumes"])


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
    version = ResumeVersion(
        family_id=family.id,
        version=1,
        status=ResumeStatus.parsing,
        file_path=f"resumes/{current_user.id}/{family.id}/v1_{file.filename}",
        file_hash=file_hash
    )
    db.add(version)
    db.commit()
    db.refresh(family)
    db.refresh(version)
    
    # TODO: Save file to storage and trigger parsing workflow
    
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
