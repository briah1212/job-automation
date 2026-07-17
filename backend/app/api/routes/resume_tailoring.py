from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agents.resume_tailoring_agent import ResumeTailoringAgent
from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models import (
    CanonicalJob,
    DocumentLock,
    ResumeClaim,
    ResumeClaimSource,
    ResumeFamily,
    ResumeStatus,
    ResumeVersion,
)
from app.schemas.resume_tailoring import ResumeTailorRequest, ResumeTailorResponse
from app.services.profile_fact_extraction import extract_facts_for_user

router = APIRouter(prefix="/resumes", tags=["resume-tailoring"])


@router.post("/{resume_version_id}/tailor", response_model=ResumeTailorResponse)
async def tailor_resume(
    resume_version_id: UUID,
    request: ResumeTailorRequest,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ResumeTailorResponse:
    """Tailor a resume version to a specific job, producing a new resume version."""
    base_version = (
        db.query(ResumeVersion)
        .join(ResumeFamily, ResumeVersion.family_id == ResumeFamily.id)
        .filter(
            ResumeVersion.id == resume_version_id,
            ResumeFamily.user_id == current_user.id,
        )
        .first()
    )
    if base_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume version not found"
        )

    job = (
        db.query(CanonicalJob)
        .filter(
            CanonicalJob.id == request.job_id,
            CanonicalJob.user_id == current_user.id,
        )
        .first()
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    profile_facts = extract_facts_for_user(db, current_user.id)

    locks = (
        db.query(DocumentLock)
        .filter(DocumentLock.resume_family_id == base_version.family_id)
        .all()
    )

    result = await ResumeTailoringAgent().tailor(
        resume_version=base_version,
        job=job,
        profile_facts=profile_facts,
        locks=locks,
    )

    max_version = (
        db.query(func.max(ResumeVersion.version))
        .filter(ResumeVersion.family_id == base_version.family_id)
        .scalar()
        or 0
    )

    new_version = ResumeVersion(
        family_id=base_version.family_id,
        parent_id=base_version.id,
        version=max_version + 1,
        status=ResumeStatus.ready,
        parsed_data=result["structured_resume"],
    )
    db.add(new_version)
    db.flush()

    claim_provenance: list[dict] = []
    for claim in result["claims"]:
        claim_row = ResumeClaim(
            resume_version_id=new_version.id,
            section=claim["section"],
            claim_text=claim["claim_text"],
        )
        db.add(claim_row)
        db.flush()

        strength = claim.get("strength", 0.0)
        profile_fact_ids: list[UUID] = []
        for fact_id_str in claim.get("source_fact_ids", []):
            fact_uuid = UUID(fact_id_str) if isinstance(fact_id_str, str) else fact_id_str
            source_row = ResumeClaimSource(
                resume_claim_id=claim_row.id,
                profile_fact_id=fact_uuid,
                strength=strength,
                explanation=f"Linked via requirement-evidence match (strength={strength:.2f})",
            )
            db.add(source_row)
            profile_fact_ids.append(fact_uuid)

        claim_provenance.append(
            {
                "claim_id": claim_row.id,
                "claim_text": claim_row.claim_text,
                "section": claim_row.section,
                "profile_fact_ids": profile_fact_ids,
            }
        )

    db.commit()
    db.refresh(new_version)

    return ResumeTailorResponse(
        resume_version_id=new_version.id,
        requirement_evidence_matrix=result["requirement_evidence_matrix"],
        change_log=result["change_log"],
        claim_provenance=claim_provenance,
        keyword_coverage=result["keyword_coverage"],
        warnings=result["warnings"],
        page_count=result["page_count"],
        quality_score=result["quality_score"],
    )
