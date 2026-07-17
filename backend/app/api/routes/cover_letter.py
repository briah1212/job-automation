from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.cover_letter_agent import CoverLetterAgent
from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models import Application, CanonicalJob, CoverLetter, ResumeVersion
from app.schemas.cover_letter import (
    CoverLetterGenerateRequest,
    CoverLetterResponse,
    CoverLetterUpdateRequest,
)
from app.services.profile_fact_extraction import extract_facts_for_user

router = APIRouter(prefix="/applications", tags=["cover-letter"])


def _get_owned_application(
    application_id: UUID, current_user, db: Session
) -> Application:
    application = (
        db.query(Application)
        .filter(Application.id == application_id, Application.user_id == current_user.id)
        .first()
    )
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Application not found"
        )
    return application


def _get_latest_cover_letter(application_id: UUID, db: Session) -> CoverLetter | None:
    return (
        db.query(CoverLetter)
        .filter(CoverLetter.application_id == application_id)
        .order_by(CoverLetter.created_at.desc())
        .first()
    )


@router.post("/{application_id}/cover-letter", response_model=CoverLetterResponse)
async def generate_cover_letter(
    application_id: UUID,
    request: CoverLetterGenerateRequest,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> CoverLetter:
    """Generate a new cover letter draft for an application. Always creates a new row."""
    application = _get_owned_application(application_id, current_user, db)

    job = db.query(CanonicalJob).filter(CanonicalJob.id == application.job_id).first()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    resume_version = None
    if application.resume_version_id is not None:
        resume_version = (
            db.query(ResumeVersion)
            .filter(ResumeVersion.id == application.resume_version_id)
            .first()
        )
    if resume_version is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No resume selected for this application yet",
        )

    profile_facts = extract_facts_for_user(db, current_user.id)

    result = await CoverLetterAgent().generate(
        application=application,
        job=job,
        resume_version=resume_version,
        profile_facts=profile_facts,
        tone=request.tone,
        word_limit=request.word_limit,
        user_id=str(current_user.id),
    )

    cover_letter = CoverLetter(
        application_id=application.id,
        content=result["content"],
        tone=request.tone,
        word_limit=request.word_limit,
        word_count=result["word_count"],
        status="needs_review",
        warnings=result["warnings"],
        claim_provenance=result["claim_provenance"],
    )
    db.add(cover_letter)
    db.commit()
    db.refresh(cover_letter)

    return cover_letter


@router.get("/{application_id}/cover-letter", response_model=CoverLetterResponse)
def get_cover_letter(
    application_id: UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> CoverLetter:
    """Return the most recently generated cover letter for an application."""
    _get_owned_application(application_id, current_user, db)

    cover_letter = _get_latest_cover_letter(application_id, db)
    if cover_letter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No cover letter has been generated yet",
        )

    return cover_letter


@router.patch("/{application_id}/cover-letter", response_model=CoverLetterResponse)
def update_cover_letter(
    application_id: UUID,
    request: CoverLetterUpdateRequest,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> CoverLetter:
    """Edit and approve the most recent cover letter for an application."""
    _get_owned_application(application_id, current_user, db)

    cover_letter = _get_latest_cover_letter(application_id, db)
    if cover_letter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No cover letter has been generated yet",
        )

    cover_letter.content = request.content
    cover_letter.word_count = len(request.content.split())
    cover_letter.status = "approved"
    db.commit()
    db.refresh(cover_letter)

    return cover_letter
