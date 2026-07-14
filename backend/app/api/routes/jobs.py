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


# Additional imports for matching and resume selection
from app.agents.matching_agent import MatchingAgent
from app.agents.resume_selection_agent import ResumeSelectionAgent
from app.models import JobMatchScore, Profile, ResumeFamily, SearchProfile
from app.schemas.job_match import JobMatchScore as JobMatchScoreSchema, ResumeSelectionResult


@router.post("/{job_id}/match", response_model=JobMatchScoreSchema, status_code=status.HTTP_201_CREATED)
def calculate_match_score(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)]
) -> JobMatchScore:
    """Calculate or recalculate match score for a job."""
    # Get job
    job = db.query(CanonicalJob).filter(
        CanonicalJob.id == job_id,
        CanonicalJob.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Get user profile
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile not found. Please complete your profile first."
        )
    
    # Get active search profile (use first enabled one)
    search_profile = db.query(SearchProfile).filter(
        SearchProfile.user_id == current_user.id,
        SearchProfile.enabled == True
    ).first()
    
    # Run matching agent
    agent = MatchingAgent()
    result = agent.score_job(job, profile, search_profile)
    
    # Check if match score exists
    existing_score = db.query(JobMatchScore).filter(
        JobMatchScore.job_id == job_id,
        JobMatchScore.user_id == current_user.id
    ).first()
    
    if existing_score:
        # Update existing
        for field, value in result.items():
            setattr(existing_score, field, value)
        match_score = existing_score
    else:
        # Create new
        match_score = JobMatchScore(
            job_id=job_id,
            user_id=current_user.id,
            **result
        )
        db.add(match_score)
    
    db.commit()
    db.refresh(match_score)
    return match_score


@router.get("/{job_id}/match", response_model=JobMatchScoreSchema)
def get_match_score(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)]
) -> JobMatchScore:
    """Get existing match score for a job."""
    match_score = db.query(JobMatchScore).filter(
        JobMatchScore.job_id == job_id,
        JobMatchScore.user_id == current_user.id
    ).first()
    
    if not match_score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match score not found. Calculate it first using POST /jobs/{job_id}/match"
        )
    
    return match_score


@router.post("/{job_id}/select-resume", response_model=ResumeSelectionResult)
def select_best_resume(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)]
) -> ResumeSelectionResult:
    """Select the best resume for this job."""
    # Get job
    job = db.query(CanonicalJob).filter(
        CanonicalJob.id == job_id,
        CanonicalJob.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Get user profile
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile not found"
        )
    
    # Get all ready resumes
    resume_families = db.query(ResumeFamily).filter(
        ResumeFamily.user_id == current_user.id
    ).all()
    
    resumes = []
    for family in resume_families:
        # Get latest version from each family
        from app.models.resume import ResumeStatus
        ready_versions = [v for v in family.versions if v.status == ResumeStatus.ready or v.status == ResumeStatus.approved]
        if ready_versions:
            # Get most recent
            latest = max(ready_versions, key=lambda v: v.created_at)
            resumes.append(latest)
    
    # Run resume selection agent
    agent = ResumeSelectionAgent()
    result = agent.select_resume(job, resumes, profile)
    
    # Update match score with selected resume
    match_score = db.query(JobMatchScore).filter(
        JobMatchScore.job_id == job_id,
        JobMatchScore.user_id == current_user.id
    ).first()
    
    if match_score and result.get("selected_resume_id"):
        match_score.matched_resume_id = result["selected_resume_id"]
        match_score.resume_selection_rationale = result["selection_rationale"]
        db.commit()
    
    return ResumeSelectionResult(**result)
