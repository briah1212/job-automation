from __future__ import annotations

from app.schemas.application import Application, ApplicationApprove, ApplicationCreate, ApplicationReview
from app.schemas.application_answer import (
    ApplicationAnswer,
    ApplicationAnswerCreate,
    ApplicationAnswerSource,
    ApplicationAnswerSourceCreate,
)
from app.schemas.application_question import ApplicationQuestion, ApplicationQuestionCreate
from app.schemas.application_review import (
    ApplicationReviewResult,
    ApplicationReviewResultCreate,
)
from app.schemas.document_lock import DocumentLock, DocumentLockCreate
from app.schemas.document_rendering import DocumentRendering, DocumentRenderingCreate
from app.schemas.job import Job, JobCreate, JobImportUrl, JobScore
from app.schemas.job_match import JobMatchScore, JobMatchScoreCreate, JobMatchScoreUpdate, ResumeSelectionResult
from app.schemas.profile import Profile, ProfileCreate, ProfileUpdate
from app.schemas.profile_fact import ProfileFact, ProfileFactCreate
from app.schemas.resume import ResumeFamily, ResumeFamilyCreate, ResumeUpload, ResumeVersion, ResumeVersionCreate
from app.schemas.resume_claim import (
    ResumeClaim,
    ResumeClaimCreate,
    ResumeClaimSource,
    ResumeClaimSourceCreate,
)
from app.schemas.reusable_answer import ReusableAnswer, ReusableAnswerCreate
from app.schemas.search_profile import SearchProfile, SearchProfileCreate, SearchProfileUpdate
from app.schemas.user import Token, User, UserCreate, UserLogin
from app.schemas.workflow import WorkflowTask, WorkflowTaskCreate

__all__ = [
    "User",
    "UserCreate",
    "UserLogin",
    "Token",
    "Profile",
    "ProfileCreate",
    "ProfileUpdate",
    "ResumeFamily",
    "ResumeFamilyCreate",
    "ResumeVersion",
    "ResumeVersionCreate",
    "ResumeUpload",
    "Job",
    "JobCreate",
    "JobImportUrl",
    "JobScore",
    "Application",
    "ApplicationCreate",
    "ApplicationReview",
    "ApplicationApprove",
    "WorkflowTask",
    "WorkflowTaskCreate",
    "SearchProfile",
    "SearchProfileCreate",
    "SearchProfileUpdate",
    "JobMatchScore",
    "JobMatchScoreCreate",
    "JobMatchScoreUpdate",
    "ResumeSelectionResult",
    "ProfileFact",
    "ProfileFactCreate",
    "ResumeClaim",
    "ResumeClaimCreate",
    "ResumeClaimSource",
    "ResumeClaimSourceCreate",
    "DocumentRendering",
    "DocumentRenderingCreate",
    "DocumentLock",
    "DocumentLockCreate",
    "ReusableAnswer",
    "ReusableAnswerCreate",
    "ApplicationQuestion",
    "ApplicationQuestionCreate",
    "ApplicationAnswer",
    "ApplicationAnswerCreate",
    "ApplicationAnswerSource",
    "ApplicationAnswerSourceCreate",
    "ApplicationReviewResult",
    "ApplicationReviewResultCreate",
]
