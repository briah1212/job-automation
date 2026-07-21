from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    application_questions,
    application_review,
    applications,
    auth,
    browser_automation,
    cover_letter,
    internal_ats_credentials,
    internal_dynamic_questions,
    internal_field_mappings,
    field_mappings,
    jobs,
    profile,
    resume_rendering,
    resume_tailoring,
    resumes,
    search_profiles,
    workflows,
)
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(resumes.router, prefix="/api")
app.include_router(resume_tailoring.router, prefix="/api")
app.include_router(resume_rendering.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(applications.router, prefix="/api")
app.include_router(application_questions.router, prefix="/api")
app.include_router(application_questions.answers_router, prefix="/api")
app.include_router(application_review.router, prefix="/api")
app.include_router(cover_letter.router, prefix="/api")
app.include_router(browser_automation.router, prefix="/api")
app.include_router(internal_ats_credentials.router, prefix="/api")
app.include_router(internal_dynamic_questions.router, prefix="/api")
app.include_router(internal_field_mappings.router, prefix="/api")
app.include_router(field_mappings.router, prefix="/api")
app.include_router(search_profiles.router, prefix="/api")
app.include_router(workflows.router, prefix="/api")


@app.get("/")
def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Job Automation Platform API"}


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
