from __future__ import annotations

from app.schemas.application import Application, ApplicationApprove, ApplicationCreate, ApplicationReview
from app.schemas.job import Job, JobCreate, JobImportUrl, JobScore
from app.schemas.profile import Profile, ProfileCreate, ProfileUpdate
from app.schemas.resume import ResumeFamily, ResumeFamilyCreate, ResumeUpload, ResumeVersion, ResumeVersionCreate
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
]
