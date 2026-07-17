from __future__ import annotations

import re
from typing import Any, Optional

from app.models import CanonicalJob, ProfileFact

_WORD_RE = re.compile(r"[a-z0-9]+")

_REQUIRED_HINTS = ("required", "must", "must-have", "mandatory", "essential")
_PREFERRED_HINTS = ("preferred", "nice to have", "nice-to-have", "bonus", "plus")

_EVIDENCE_THRESHOLD = 0.15
_STRONG_COVERAGE_THRESHOLD = 0.6
_PARTIAL_COVERAGE_THRESHOLD = 0.3


def _words(text: str) -> set[str]:
    """Split text into a lowercase set of word tokens."""
    return set(_WORD_RE.findall((text or "").lower()))


def _overlap_ratio(a: set[str], b: set[str]) -> float:
    """Compute a simple Jaccard-style overlap ratio between two word sets."""
    if not a or not b:
        return 0.0
    intersection = a & b
    if not intersection:
        return 0.0
    union = a | b
    return len(intersection) / len(union)


def _determine_importance(requirement: str, description: Optional[str]) -> str:
    """Determine whether a requirement is "required" or "preferred".

    Checks the requirement text itself first, then falls back to scanning a
    window of the raw job description text (if present) around the
    requirement's mention for qualifier hints.
    """
    req_lower = requirement.lower()

    if any(hint in req_lower for hint in _PREFERRED_HINTS):
        return "preferred"
    if any(hint in req_lower for hint in _REQUIRED_HINTS):
        return "required"

    if description:
        desc_lower = description.lower()
        idx = desc_lower.find(req_lower)
        if idx != -1:
            window_start = max(0, idx - 100)
            window_end = idx + len(req_lower) + 100
            window = desc_lower[window_start:window_end]
            if any(hint in window for hint in _PREFERRED_HINTS):
                return "preferred"
            if any(hint in window for hint in _REQUIRED_HINTS):
                return "required"

    # No qualifier hints found anywhere - default to required.
    return "required"


def _determine_coverage(evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return "none"

    top_strength = evidence[0]["strength"]
    if top_strength > _STRONG_COVERAGE_THRESHOLD:
        return "strong"
    if top_strength > _PARTIAL_COVERAGE_THRESHOLD:
        return "partial"
    return "none"


def build_requirement_evidence_matrix(
    job: CanonicalJob, profile_facts: list[ProfileFact]
) -> list[dict[str, Any]]:
    """Build a requirement-evidence matrix linking job requirements to supporting facts.

    For each requirement string found in job.extracted_data["requirements"]
    (falling back to job.extracted_data["skills"] if absent), scores each
    ProfileFact against it via case-insensitive keyword overlap, keeping
    facts with a strength above the evidence threshold as supporting
    evidence.
    """
    extracted_data = job.extracted_data or {}

    requirements = extracted_data.get("requirements")
    if not requirements:
        requirements = extracted_data.get("skills")
    if not requirements:
        return []

    description = job.description or ""

    matrix: list[dict[str, Any]] = []

    for requirement in requirements:
        requirement_text = str(requirement)
        requirement_words = _words(requirement_text)

        evidence: list[dict[str, Any]] = []
        for fact in profile_facts:
            fact_words = _words(fact.content)
            strength = _overlap_ratio(requirement_words, fact_words)
            if strength > _EVIDENCE_THRESHOLD:
                matched_keywords = sorted(requirement_words & fact_words)
                explanation = (
                    f"Matched keywords: {', '.join(matched_keywords)}"
                    if matched_keywords
                    else "Matched keywords: (none)"
                )
                evidence.append(
                    {
                        "profile_fact_id": str(fact.id),
                        "strength": round(strength, 4),
                        "explanation": explanation,
                    }
                )

        evidence.sort(key=lambda e: e["strength"], reverse=True)

        matrix.append(
            {
                "requirement": requirement_text,
                "importance": _determine_importance(requirement_text, description),
                "evidence": evidence,
                "coverage": _determine_coverage(evidence),
            }
        )

    return matrix
