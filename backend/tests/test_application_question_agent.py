"""Tests for the application question agent, reusable-answer matching, and experience calculator."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from uuid import uuid4

from app.agents.application_question_agent import ApplicationQuestionAgent
from app.models import ProfileFact, ReusableAnswer
from app.services.experience_calculator import calculate_years_of_experience
from app.services.reusable_answer_matching import find_matching_reusable_answer


def _make_reusable_answer(
    canonical_question: str,
    exact_answer: str,
    semantic_variants=None,
    user_approved: bool = True,
) -> ReusableAnswer:
    return ReusableAnswer(
        id=uuid4(),
        user_id=uuid4(),
        canonical_question=canonical_question,
        semantic_variants=semantic_variants or [],
        exact_answer=exact_answer,
        allowed_paraphrasing=False,
        risk_level="low",
        categories=[],
        user_approved=user_approved,
    )


def _make_profile_fact(fact_type: str, content: str, original_text: str = None) -> ProfileFact:
    return ProfileFact(
        id=uuid4(),
        user_id=uuid4(),
        fact_type=fact_type,
        content=content,
        source_type="resume_upload",
        source_identifier=None,
        original_text=original_text,
        confidence=0.8,
        user_verified=False,
        permitted_uses=[],
    )


class TestFindMatchingReusableAnswer:
    """Tests for find_matching_reusable_answer."""

    def test_exact_canonical_match(self):
        answer = _make_reusable_answer(
            "What is your full legal name?", "Jane Doe"
        )
        result = find_matching_reusable_answer(
            "What is your full legal name?", [answer]
        )
        assert result is answer

    def test_exact_match_ignores_punctuation_and_case(self):
        answer = _make_reusable_answer(
            "What is your full legal name?", "Jane Doe"
        )
        result = find_matching_reusable_answer(
            "  WHAT IS YOUR FULL LEGAL NAME  ", [answer]
        )
        assert result is answer

    def test_semantic_variant_match(self):
        answer = _make_reusable_answer(
            "What is your full legal name?",
            "Jane Doe",
            semantic_variants=["What's your legal name?"],
        )
        result = find_matching_reusable_answer(
            "What's your legal name?", [answer]
        )
        assert result is answer

    def test_no_match_returns_none(self):
        answer = _make_reusable_answer(
            "What is your full legal name?", "Jane Doe"
        )
        result = find_matching_reusable_answer(
            "What is your greatest weakness?", [answer]
        )
        assert result is None

    def test_prefers_approved_match(self):
        unapproved = _make_reusable_answer(
            "What is your full legal name?", "Wrong Name", user_approved=False
        )
        approved = _make_reusable_answer(
            "What is your full legal name?", "Jane Doe", user_approved=True
        )
        result = find_matching_reusable_answer(
            "What is your full legal name?", [unapproved, approved]
        )
        assert result is approved


class TestCalculateYearsOfExperience:
    """Tests for calculate_years_of_experience."""

    def test_extracts_years_from_clear_date_range(self):
        fact = _make_profile_fact(
            "experience_bullet",
            "Software Engineer at Acme Corp working with Python, 2018-2022",
        )
        result = calculate_years_of_experience([fact], "python")
        assert result["years"] is not None
        assert result["years"] == pytest.approx(4.0, abs=0.1)
        assert len(result["calculation_basis"]) == 1
        assert result["calculation_basis"][0]["fact_id"] == str(fact.id)

    def test_no_date_info_returns_none_with_warning(self):
        fact = _make_profile_fact(
            "experience_bullet",
            "Built scalable Python services for a large e-commerce platform",
        )
        result = calculate_years_of_experience([fact], "python")
        assert result["years"] is None
        assert result["calculation_basis"] == []
        assert "warning" in result
        assert "user input required" in result["warning"]

    def test_non_overlapping_policy_merges_overlaps(self):
        fact1 = _make_profile_fact(
            "experience_bullet", "Python developer, 2015-2019"
        )
        fact2 = _make_profile_fact(
            "experience_bullet", "Python backend engineer, 2018-2021"
        )
        result = calculate_years_of_experience(
            [fact1, fact2], "python", policy="non_overlapping"
        )
        # Overlapping 2015-2019 and 2018-2021 merge into 2015-2021 = 6 years.
        assert result["years"] == pytest.approx(6.0, abs=0.2)


class TestApplicationQuestionAgent:
    """Tests for ApplicationQuestionAgent.generate_answer."""

    @pytest.mark.asyncio
    async def test_high_risk_without_match_needs_user_input(self):
        agent = ApplicationQuestionAgent()
        result = await agent.generate_answer(
            question_text="Are you legally authorized to work in this country?",
            question_type="work_authorization",
            risk_level="high",
            profile_facts=[],
            reusable_answers=[],
            user_id=str(uuid4()),
        )
        assert result["needs_user_input"] is True
        assert result["answer_text"] == ""
        assert result["source"] == "user_input"
        assert result["approved"] is False

    @pytest.mark.asyncio
    async def test_low_risk_with_reusable_answer_match(self):
        answer = _make_reusable_answer(
            "What is your full legal name?", "Jane Doe", user_approved=True
        )
        agent = ApplicationQuestionAgent()
        result = await agent.generate_answer(
            question_text="What is your full legal name?",
            question_type="personal_info",
            risk_level="low",
            profile_facts=[],
            reusable_answers=[answer],
            user_id=str(uuid4()),
        )
        assert result["answer_text"] == "Jane Doe"
        assert result["source"] == "exact_approved"
        assert result["approved"] is True
        assert result["needs_user_input"] is False

    @pytest.mark.asyncio
    async def test_ai_generated_refusal_text_is_not_used_as_literal_answer(self):
        """CRITICAL, confirmed live against a real Jobvite posting
        (NinjaOne): the AI-generated path's own prompt tells the model to
        say so when the facts don't cover the question - the model
        followed that instruction correctly ("The provided facts do not
        include any information about a city."), but that prose then got
        typed straight into the real "City" field on a live application as
        if it were a genuine answer. A response indicating the model
        couldn't actually answer must escalate to needs_user_input, not be
        returned as a usable value."""
        with patch(
            "app.ai_gateway.gateway.AIGateway.generate_text",
            new=AsyncMock(return_value="The provided facts do not include any information about a city."),
        ):
            agent = ApplicationQuestionAgent()
            result = await agent.generate_answer(
                question_text="What city do you live in?",
                question_type="personal_info",
                risk_level="medium",
                profile_facts=[],
                reusable_answers=[],
                user_id=str(uuid4()),
            )
        assert result["needs_user_input"] is True
        assert result["answer_text"] == ""

    @pytest.mark.asyncio
    async def test_ai_generated_real_answer_is_still_used(self):
        """The fix must not swallow genuine answers - only ones that
        actually indicate the model couldn't answer."""
        with patch(
            "app.ai_gateway.gateway.AIGateway.generate_text",
            new=AsyncMock(return_value="San Francisco, California"),
        ):
            agent = ApplicationQuestionAgent()
            result = await agent.generate_answer(
                question_text="What city do you live in?",
                question_type="personal_info",
                risk_level="medium",
                profile_facts=[],
                reusable_answers=[],
                user_id=str(uuid4()),
            )
        assert result["needs_user_input"] is False
        assert result["answer_text"] == "San Francisco, California"

    @pytest.mark.asyncio
    async def test_expects_short_answer_changes_the_prompt_length_instruction(self):
        """CRITICAL, confirmed live against a real Pinpoint posting
        (Confluence Technologies): a field labeled "Town" (no FieldMapper
        rule covered it - see the fix in field_mapper.py) reached this
        AI-generated path, and the blanket "Keep the answer concise
        (1-3 sentences)" instruction produced a full personal-summary-
        style paragraph for what needed to be a single town name.
        expects_short_answer=True must swap in a short-value instruction
        instead."""
        captured_prompt = {}

        async def _capture_prompt(prompt, **kwargs):
            captured_prompt["value"] = prompt
            return "Ann Arbor"

        with patch(
            "app.ai_gateway.gateway.AIGateway.generate_text",
            new=AsyncMock(side_effect=_capture_prompt),
        ):
            agent = ApplicationQuestionAgent()
            result = await agent.generate_answer(
                question_text="Town",
                question_type="personal_info",
                risk_level="medium",
                profile_facts=[],
                reusable_answers=[],
                user_id=str(uuid4()),
                expects_short_answer=True,
            )
        assert result["answer_text"] == "Ann Arbor"
        assert "short phrase or single value" in captured_prompt["value"]
        assert "1-3 sentences" not in captured_prompt["value"]

    @pytest.mark.asyncio
    async def test_expects_short_answer_false_keeps_the_original_prompt(self):
        captured_prompt = {}

        async def _capture_prompt(prompt, **kwargs):
            captured_prompt["value"] = prompt
            return "A longer, open-ended answer."

        with patch(
            "app.ai_gateway.gateway.AIGateway.generate_text",
            new=AsyncMock(side_effect=_capture_prompt),
        ):
            agent = ApplicationQuestionAgent()
            await agent.generate_answer(
                question_text="Tell us about yourself",
                question_type="personal_info",
                risk_level="medium",
                profile_facts=[],
                reusable_answers=[],
                user_id=str(uuid4()),
                expects_short_answer=False,
            )
        assert "1-3 sentences" in captured_prompt["value"]
