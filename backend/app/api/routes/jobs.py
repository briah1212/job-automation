from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models import CanonicalJob, JobStatus
from app.schemas import JobCreate, JobImportUrl, JobScore
from app.schemas.job import Job as JobSchema

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobSchema])
def list_jobs(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    status_filter: Optional[JobStatus] = None,
    skip: int = 0,
    limit: int = 100
) -> list[CanonicalJob]:
    """List all jobs for current user."""
    query = db.query(CanonicalJob).filter(CanonicalJob.user_id == current_user.id)
    
    if status_filter:
        query = query.filter(CanonicalJob.status == status_filter)
    
    jobs = query.order_by(CanonicalJob.created_at.desc()).offset(skip).limit(limit).all()
    return jobs


@router.get("/{job_id}", response_model=JobSchema)
def get_job(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)]
) -> CanonicalJob:
    """Get a specific job."""
    job = db.query(CanonicalJob).filter(
        CanonicalJob.id == job_id,
        CanonicalJob.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return job


@router.post("/import-url", response_model=JobSchema, status_code=status.HTTP_201_CREATED)
def import_job_from_url(
    job_import: JobImportUrl,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)]
) -> CanonicalJob:
    """Import a job from a URL."""
    # Create job with extracting status
    job = CanonicalJob(
        user_id=current_user.id,
        company="",
        title="",
        status=JobStatus.extracting,
        extracted_data={"url": job_import.url}
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # TODO: Trigger extraction workflow
    
    return job


@router.post("/{job_id}/score", response_model=JobSchema)
def score_job(
    job_id: uuid.UUID,
    score_data: JobScore,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)]
) -> CanonicalJob:
    """Score a job."""
    job = db.query(CanonicalJob).filter(
        CanonicalJob.id == job_id,
        CanonicalJob.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    job.score = score_data.score
    job.status = JobStatus.scored
    db.commit()
    db.refresh(job)
    return job
