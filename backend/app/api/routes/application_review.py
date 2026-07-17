from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.application_review_agent import ApplicationReviewAgent
from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models import (
    Application,
    ApplicationAnswer,
    ApplicationQuestion,
    ApplicationReview,
    ApplicationStatus,
    CanonicalJob,
    ResumeVersion,
)
from app.schemas.application_review import ApplicationReviewResult

router = APIRouter(prefix="/applications", tags=["application-review"])


def _load_owned_application(application_id: uuid.UUID, current_user, db: Session) -> Application:
    """Load an application, scoped to the current user, or raise 404."""
    application = db.query(Application).filter(
        Application.id == application_id,
        Application.user_id == current_user.id,
    ).first()
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


def _build_questions_and_answers(application_id: uuid.UUID, db: Session) -> list[dict]:
    """Join ApplicationQuestion -> ApplicationAnswer into the plain-dict shape the agent expects."""
    rows = (
        db.query(ApplicationQuestion, ApplicationAnswer)
        .outerjoin(ApplicationAnswer, ApplicationAnswer.application_question_id == ApplicationQuestion.id)
        .filter(ApplicationQuestion.application_id == application_id)
        .all()
    )

    questions_and_answers = []
    for question, answer in rows:
        answer_text = answer.answer_text if answer is not None else ""
        questions_and_answers.append({
            "question_text": question.question_text,
            "question_type": question.question_type,
            "risk_level": question.risk_level,
            "answer_text": answer_text,
            "answered": bool(answer is not None and answer_text and answer_text.strip()),
        })
    return questions_and_answers


@router.post("/{application_id}/auto-review", response_model=ApplicationReviewResult)
async def auto_review_application(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ApplicationReview:
    """Run the automated ApplicationReviewAgent against an application and persist the result."""
    application = _load_owned_application(application_id, current_user, db)

    job = db.query(CanonicalJob).filter(CanonicalJob.id == application.job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found for application")

    resume_version = None
    if application.resume_version_id is not None:
        resume_version = db.query(ResumeVersion).filter(
            ResumeVersion.id == application.resume_version_id
        ).first()

    questions_and_answers = _build_questions_and_answers(application.id, db)

    is_duplicate = db.query(Application).filter(
        Application.user_id == application.user_id,
        Application.job_id == application.job_id,
        Application.id != application.id,
        Application.status != ApplicationStatus.draft,
    ).first() is not None

    result = await ApplicationReviewAgent().review(
        application=application,
        job=job,
        resume_version=resume_version,
        questions_and_answers=questions_and_answers,
        is_duplicate=is_duplicate,
    )

    review = ApplicationReview(
        application_id=application.id,
        passed=result["passed"],
        blocking_findings=[{"message": finding} for finding in result["blocking_findings"]],
        warnings=[{"message": warning} for warning in result["warnings"]],
        confidence=result["confidence"],
        recommended_correction=result["recommended_correction"],
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@router.get("/{application_id}/review-result", response_model=ApplicationReviewResult)
def get_latest_review_result(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ApplicationReview:
    """Return the most recent automated review result recorded for an application."""
    application = _load_owned_application(application_id, current_user, db)

    review = (
        db.query(ApplicationReview)
        .filter(ApplicationReview.application_id == application.id)
        .order_by(ApplicationReview.created_at.desc())
        .first()
    )
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No review has been run yet")
    return review
