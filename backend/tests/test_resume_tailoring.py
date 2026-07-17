"""Tests for the resume tailoring feature: requirement-evidence matrix and tailoring agent."""
from __future__ import annotations

import pytest
from uuid import uuid4

from app.agents.resume_tailoring_agent import ResumeTailoringAgent
from app.models import CanonicalJob, DocumentLock, ProfileFact, ResumeVersion
from app.services.requirement_evidence import build_requirement_evidence_matrix


def _make_fact(content: str) -> ProfileFact:
    return ProfileFact(
        id=uuid4(),
        user_id=uuid4(),
        fact_type="skill",
        content=content,
        source_type="resume_upload",
        confidence=0.9,
        user_verified=True,
        permitted_uses=[],
    )


class TestBuildRequirementEvidenceMatrix:
    """Test the requirement-evidence matrix scoring logic."""

    def test_scores_matching_and_non_matching_facts(self):
        job = CanonicalJob(
            id=uuid4(),
            user_id=uuid4(),
            company="Acme",
            title="Data Engineer",
            description="Requirements: python programming. Preferred: kubernetes orchestration (nice to have).",
            extracted_data={"requirements": ["python programming", "kubernetes orchestration (nice to have)"]},
        )

        fact_strong = _make_fact("python programming")
        fact_unrelated = _make_fact("java enterprise systems")

        matrix = build_requirement_evidence_matrix(job, [fact_strong, fact_unrelated])

        assert len(matrix) == 2

        req0 = matrix[0]
        assert req0["requirement"] == "python programming"
        assert req0["coverage"] == "strong"
        assert req0["evidence"][0]["profile_fact_id"] == str(fact_strong.id)
        assert req0["evidence"][0]["strength"] == pytest.approx(1.0)
        assert "Matched keywords" in req0["evidence"][0]["explanation"]
        # Unrelated fact should not show up as evidence at all.
        assert all(e["profile_fact_id"] != str(fact_unrelated.id) for e in req0["evidence"])

        req1 = matrix[1]
        assert req1["coverage"] == "none"
        assert req1["evidence"] == []
        assert req1["importance"] == "preferred"

    def test_falls_back_to_skills_and_handles_empty(self):
        job_with_skills = CanonicalJob(
            id=uuid4(),
            user_id=uuid4(),
            company="Acme",
            title="Engineer",
            extracted_data={"skills": ["Go"]},
        )
        matrix = build_requirement_evidence_matrix(job_with_skills, [])
        assert len(matrix) == 1
        assert matrix[0]["requirement"] == "Go"
        assert matrix[0]["evidence"] == []

        job_empty = CanonicalJob(
            id=uuid4(), user_id=uuid4(), company="Acme", title="Engineer", extracted_data={}
        )
        assert build_requirement_evidence_matrix(job_empty, []) == []


class TestResumeTailoringAgent:
    """Test the ResumeTailoringAgent, including lock enforcement."""

    def _build_job_and_fact(self):
        job = CanonicalJob(
            id=uuid4(),
            user_id=uuid4(),
            company="Acme",
            title="Data Engineer",
            description="Python and Spark experience required.",
            extracted_data={"requirements": ["Python", "Spark"]},
        )
        fact = _make_fact("Python")
        return job, fact

    @pytest.mark.asyncio
    async def test_tailor_returns_expected_shape_and_claims(self):
        agent = ResumeTailoringAgent()
        job, fact = self._build_job_and_fact()

        family_id = uuid4()
        resume_version = ResumeVersion(
            id=uuid4(),
            family_id=family_id,
            version=1,
            parsed_data={"summary": "Original summary.", "skills": ["Python"]},
        )

        result = await agent.tailor(
            resume_version=resume_version, job=job, profile_facts=[fact], locks=[]
        )

        assert set(result.keys()) == {
            "structured_resume",
            "requirement_evidence_matrix",
            "claims",
            "change_log",
            "keyword_coverage",
            "warnings",
            "page_count",
            "quality_score",
        }
        assert isinstance(result["structured_resume"], dict)
        assert isinstance(result["requirement_evidence_matrix"], list)
        assert isinstance(result["claims"], list)
        assert len(result["claims"]) > 0

        # No locks supplied - no lock-enforcement warnings should be present.
        assert not any("enforced" in w for w in result["warnings"])

        # Every claim should have at least a fallback source fact (best matrix evidence).
        for claim in result["claims"]:
            assert claim["source_fact_ids"] == [str(fact.id)]
            assert claim["strength"] > 0

    @pytest.mark.asyncio
    async def test_tailor_enforces_locked_fields(self):
        agent = ResumeTailoringAgent()
        job, fact = self._build_job_and_fact()

        family_id = uuid4()
        original_summary = "Original truthful summary that must not be changed by the AI."
        resume_version = ResumeVersion(
            id=uuid4(),
            family_id=family_id,
            version=1,
            parsed_data={"summary": original_summary, "skills": ["Python"]},
        )

        # Sanity check: without a lock, the mock provider's placeholder output
        # overwrites the summary field.
        unlocked_result = await agent.tailor(
            resume_version=resume_version, job=job, profile_facts=[fact], locks=[]
        )
        assert unlocked_result["structured_resume"]["summary"] != original_summary

        lock = DocumentLock(
            id=uuid4(),
            resume_family_id=family_id,
            lock_type="exact_title",
            target_ref="summary",
            value=None,
        )

        locked_result = await agent.tailor(
            resume_version=resume_version, job=job, profile_facts=[fact], locks=[lock]
        )

        # Lock must be enforced: the summary is reverted to its original value.
        assert locked_result["structured_resume"]["summary"] == original_summary
        assert any("Lock 'exact_title' enforced" in w for w in locked_result["warnings"])
