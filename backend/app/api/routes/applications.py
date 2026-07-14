from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models import Application, ApplicationPipelineStatus, ApplicationStatus
from app.schemas import ApplicationApprove, ApplicationCreate, ApplicationReview
from app.schemas.application import Application as ApplicationSchema

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationSchema])
def list_applications(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    skip: int = 0,
    limit: int = 100
) -> list[Application]:
    """List all applications for current user."""
    applications = db.query(Application).filter(
        Application.user_id == current_user.id
    ).order_by(Application.created_at.desc()).offset(skip).limit(limit).all()
    return applications


@router.get("/{application_id}", response_model=ApplicationSchema)
def get_application(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)]
) -> Application:
    """Get a specific application."""
    application = db.query(Application).filter(
        Application.id == application_id,
        Application.user_id == current_user.id
    ).first()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    return application


@router.post("", response_model=ApplicationSchema, status_code=status.HTTP_201_CREATED)
def create_application(
    application_in: ApplicationCreate,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)]
) -> Application:
    """Create a new application."""
    application = Application(
        user_id=current_user.id,
        job_id=application_in.job_id,
        resume_version_id=application_in.resume_version_id,
        status=ApplicationStatus.draft,
        pipeline_status=ApplicationPipelineStatus.draft
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


@router.post("/{application_id}/review", response_model=ApplicationSchema)
def review_application(
    application_id: uuid.UUID,
    review_data: ApplicationReview,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)]
) -> Application:
    """Review an application."""
    application = db.query(Application).filter(
        Application.id == application_id,
        Application.user_id == current_user.id
    ).first()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    application.review_result = {
        "approved": review_data.approved,
        "comments": review_data.comments
    }
    application.pipeline_status = ApplicationPipelineStatus.approved if review_data.approved else ApplicationPipelineStatus.draft
    db.commit()
    db.refresh(application)
    return application


@router.post("/{application_id}/approve", response_model=ApplicationSchema)
def approve_application(
    application_id: uuid.UUID,
    approve_data: ApplicationApprove,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)]
) -> Application:
    """Approve an application for submission."""
    application = db.query(Application).filter(
        Application.id == application_id,
        Application.user_id == current_user.id
    ).first()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    if approve_data.approved:
        application.status = ApplicationStatus.ready
        application.pipeline_status = ApplicationPipelineStatus.approved
    else:
        application.status = ApplicationStatus.draft
        application.pipeline_status = ApplicationPipelineStatus.draft
    
    db.commit()
    db.refresh(application)
    return application
