from pydantic import BaseModel, Field
from typing import Optional


class ExtractedJob(BaseModel):
    company: str
    title: str
    location: Optional[str] = None
    remote_policy: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    experience_years_min: Optional[int] = None


class JobClassification(BaseModel):
    primary_category: str
    secondary_categories: list[str] = Field(default_factory=list)
    confidence: float
    explanation: str


class MatchScore(BaseModel):
    overall_score: int
    dimension_scores: dict[str, float]
    hard_blockers: list[str] = Field(default_factory=list)
    strong_matches: list[str] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    recommended_action: str
    explanation: str


class ResumeSelection(BaseModel):
    selected_resume_id: str
    selection_rationale: str
    missing_coverage: list[str] = Field(default_factory=list)
    tailoring_recommended: bool


class ResumeTailoring(BaseModel):
    structured_resume: dict
    changelog: list[dict] = Field(default_factory=list)
    claim_provenance: list[dict] = Field(default_factory=list)
    keyword_coverage: dict[str, bool] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    page_count_estimate: int = 1
    quality_score: float = 0.0


class CoverLetterDraft(BaseModel):
    content: str
    word_count: int
    warnings: list[str] = Field(default_factory=list)


class ReviewResult(BaseModel):
    passed: bool
    blocking_findings: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: float
