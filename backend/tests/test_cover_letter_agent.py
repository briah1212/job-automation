"""Tests for the Cover Letter Agent."""
from __future__ import annotations

import pytest
from uuid import uuid4

from app.agents.cover_letter_agent import CoverLetterAgent
from app.models import CanonicalJob, ProfileFact, ResumeVersion


def _make_fact(content: str) -> ProfileFact:
    return ProfileFact(
        id=uuid4(),
        user_id=uuid4(),
        fact_type="experience_bullet",
        content=content,
        source_type="resume_upload",
        confidence=0.9,
        user_verified=True,
        permitted_uses=[],
    )


def _make_job() -> CanonicalJob:
    return CanonicalJob(
        id=uuid4(),
        user_id=uuid4(),
        company="Acme Corp",
        title="Senior Data Engineer",
        description="We need someone with real-time pipeline experience.",
        extracted_data={"requirements": ["real-time data pipelines", "data warehouse optimization"]},
    )


def _make_resume_version() -> ResumeVersion:
    return ResumeVersion(
        id=uuid4(),
        family_id=uuid4(),
        version=1,
        parsed_data={
            "summary": "Senior data engineer with 6+ years of experience.",
            "experience": [
                {
                    "company": "Tech Corp",
                    "title": "Senior Data Engineer",
                    "achievements": ["Built real-time data pipeline processing 10M events/day"],
                }
            ],
        },
    )


class TestCoverLetterAgent:
    """Test the CoverLetterAgent using the mock AI provider."""

    @pytest.mark.asyncio
    async def test_generate_returns_expected_shape(self):
        agent = CoverLetterAgent()
        job = _make_job()
        resume_version = _make_resume_version()
        fact = _make_fact("Led migration of legacy ETL jobs to Airflow")

        result = await agent.generate(
            application=None,
            job=job,
            resume_version=resume_version,
            profile_facts=[fact],
            tone=None,
            word_limit=None,
            user_id=str(uuid4()),
        )

        assert set(result.keys()) == {"content", "word_count", "warnings", "claim_provenance"}
        assert isinstance(result["content"], str) and result["content"].strip()
        assert isinstance(result["word_count"], int) and result["word_count"] > 0
        assert isinstance(result["warnings"], list)
        assert isinstance(result["claim_provenance"], list)

    @pytest.mark.asyncio
    async def test_claim_provenance_includes_matching_fact(self):
        agent = CoverLetterAgent()
        job = _make_job()
        resume_version = _make_resume_version()

        # The mock provider's canned response text includes this exact phrase, so this
        # fact should show up in claim_provenance.
        matching_fact = _make_fact("built real-time data pipelines")
        unrelated_fact = _make_fact("Certified Kubernetes Administrator")

        result = await agent.generate(
            application=None,
            job=job,
            resume_version=resume_version,
            profile_facts=[matching_fact, unrelated_fact],
            tone=None,
            word_limit=None,
            user_id=str(uuid4()),
        )

        provenance_fact_ids = {entry["profile_fact_id"] for entry in result["claim_provenance"]}
        assert str(matching_fact.id) in provenance_fact_ids
        assert str(unrelated_fact.id) not in provenance_fact_ids

    @pytest.mark.asyncio
    async def test_warns_when_word_limit_exceeded(self):
        agent = CoverLetterAgent()
        job = _make_job()
        resume_version = _make_resume_version()

        # The mock response is well over 20 words, so a small word_limit should trigger
        # the exceeded-limit warning.
        result = await agent.generate(
            application=None,
            job=job,
            resume_version=resume_version,
            profile_facts=[],
            tone=None,
            word_limit=20,
            user_id=str(uuid4()),
        )

        assert result["word_count"] > 20 * 1.1
        assert "Generated content exceeds the requested word limit." in result["warnings"]

    @pytest.mark.asyncio
    async def test_no_warning_when_within_word_limit(self):
        agent = CoverLetterAgent()
        job = _make_job()
        resume_version = _make_resume_version()

        result = await agent.generate(
            application=None,
            job=job,
            resume_version=resume_version,
            profile_facts=[],
            tone="professional",
            word_limit=1000,
            user_id=str(uuid4()),
        )

        assert "Generated content exceeds the requested word limit." not in result["warnings"]
