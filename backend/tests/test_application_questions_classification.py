"""Tests for the keyword-based risk/type classifier in application_questions.py.

Covers EEO/demographic self-identification terms confirmed as real, named
fields across Workday, Greenhouse, Ashby, and Lever during real-ATS
validation - these must classify as high risk so ApplicationQuestionAgent's
never-guess rule applies to them.
"""
from __future__ import annotations

import pytest

from app.api.routes.application_questions import _infer_question_type, _infer_risk_level


@pytest.mark.parametrize(
    "question_text",
    [
        "Gender",
        "Race/Ethnicity",
        "Hispanic or Latino",
        "Veteran Status",
        "Voluntary Self-Identification of Disability",
        "What is your race?",
        "Are you a protected veteran?",
    ],
)
def test_eeo_demographic_questions_are_high_risk(question_text):
    assert _infer_risk_level(question_text) == "high"


@pytest.mark.parametrize(
    "question_text",
    [
        "Gender",
        "Race/Ethnicity",
        "Veteran Status",
        "Disability Status",
    ],
)
def test_eeo_demographic_questions_have_dedicated_type(question_text):
    assert _infer_question_type(question_text) == "demographic_self_id"


@pytest.mark.parametrize(
    "question_text,expected",
    [
        ("Are you legally authorized to work in this country?", "high"),
        ("Do you require visa sponsorship?", "high"),
        ("What are your salary expectations?", "medium"),
        ("What is your full legal name?", "low"),
    ],
)
def test_existing_risk_tiers_unaffected(question_text, expected):
    assert _infer_risk_level(question_text) == expected
