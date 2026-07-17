"""Tests for the ApplicationReviewAgent."""
from __future__ import annotations

import pytest
from uuid import uuid4

from app.agents.application_review_agent import ApplicationReviewAgent
from app.models import Application, CanonicalJob, ResumeVersion

# NOTE on MockProvider behavior: AIGateway defaults to the "mock" provider (AI_PROVIDER=mock
# in this environment). MockProvider.generate_json() routes on the schema title / prompt
# keywords - since our prompt template's schema is ReviewResult and the prompt text contains
# the word "review", MockProvider._mock_review_result() is used, which always returns:
#   {"passed": True, "blocking_findings": [], "warnings": [], "confidence": 0.92}
# So the AI pass never contributes additional findings in these tests; all
# blocking_findings/warnings below come from the deterministic checks.


def _make_job(company: str = "Acme Corp", title: str = "Senior Engineer") -> CanonicalJob:
    return CanonicalJob(
        id=uuid4(),
        user_id=uuid4(),
        company=company,
        title=title,
        extracted_data={},
    )


def _make_application(user_id=None) -> Application:
    return Application(
        id=uuid4(),
        user_id=user_id or uuid4(),
        job_id=uuid4(),
    )


def _make_resume_version() -> ResumeVersion:
    return ResumeVersion(
        id=uuid4(),
        family_id=uuid4(),
        version=1,
        parsed_data={"summary": "Experienced backend engineer with 6 years of Python."},
    )


@pytest.mark.asyncio
async def test_clean_application_passes():
    """A clean application (resume present, all high-risk answered, no placeholders) passes."""
    agent = ApplicationReviewAgent()
    application = _make_application()
    job = _make_job()
    resume_version = _make_resume_version()

    questions_and_answers = [
        {
            "question_text": "Why do you want to work here?",
            "question_type": "text",
            "risk_level": "high",
            "answer_text": "I'm excited about Acme Corp's mission and this Senior Engineer role.",
            "answered": True,
        },
        {
            "question_text": "What is your notice period?",
            "question_type": "text",
            "risk_level": "low",
            "answer_text": "Two weeks.",
            "answered": True,
        },
    ]

    result = await agent.review(
        application=application,
        job=job,
        resume_version=resume_version,
        questions_and_answers=questions_and_answers,
        is_duplicate=False,
    )

    assert result["passed"] is True
    assert result["blocking_findings"] == []
    assert result["recommended_correction"] is None
    assert 0.0 <= result["confidence"] <= 1.0


@pytest.mark.asyncio
async def test_missing_resume_is_blocking():
    """No resume_version attached should produce a blocking finding and passed=False."""
    agent = ApplicationReviewAgent()
    application = _make_application()
    job = _make_job()

    result = await agent.review(
        application=application,
        job=job,
        resume_version=None,
        questions_and_answers=[],
        is_duplicate=False,
    )

    assert result["passed"] is False
    assert any("No resume selected" in finding for finding in result["blocking_findings"])
    assert result["recommended_correction"] is not None


@pytest.mark.asyncio
async def test_unanswered_high_risk_question_is_blocking():
    """An unanswered high-risk question should produce a blocking finding."""
    agent = ApplicationReviewAgent()
    application = _make_application()
    job = _make_job()
    resume_version = _make_resume_version()

    questions_and_answers = [
        {
            "question_text": "Have you ever been terminated for cause?",
            "question_type": "boolean",
            "risk_level": "high",
            "answer_text": "",
            "answered": False,
        },
    ]

    result = await agent.review(
        application=application,
        job=job,
        resume_version=resume_version,
        questions_and_answers=questions_and_answers,
        is_duplicate=False,
    )

    assert result["passed"] is False
    assert any(
        "Unanswered high-risk question" in finding and "terminated for cause" in finding
        for finding in result["blocking_findings"]
    )


@pytest.mark.asyncio
async def test_placeholder_text_is_blocking():
    """Placeholder markers left in an answer should produce a blocking finding."""
    agent = ApplicationReviewAgent()
    application = _make_application()
    job = _make_job()
    resume_version = _make_resume_version()

    questions_and_answers = [
        {
            "question_text": "Describe a challenging project.",
            "question_type": "text",
            "risk_level": "low",
            "answer_text": "TODO: fill this in",
            "answered": True,
        },
    ]

    result = await agent.review(
        application=application,
        job=job,
        resume_version=resume_version,
        questions_and_answers=questions_and_answers,
        is_duplicate=False,
    )

    assert result["passed"] is False
    assert any("Placeholder text" in finding for finding in result["blocking_findings"])


@pytest.mark.asyncio
async def test_duplicate_application_is_blocking():
    """is_duplicate=True should produce a blocking finding."""
    agent = ApplicationReviewAgent()
    application = _make_application()
    job = _make_job()
    resume_version = _make_resume_version()

    result = await agent.review(
        application=application,
        job=job,
        resume_version=resume_version,
        questions_and_answers=[],
        is_duplicate=True,
    )

    assert result["passed"] is False
    assert any("duplicate" in finding.lower() or "already exists" in finding.lower()
                for finding in result["blocking_findings"])
