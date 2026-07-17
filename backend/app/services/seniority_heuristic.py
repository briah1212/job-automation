from __future__ import annotations

from typing import Optional


def infer_seniority(title: str, experience_years_min: Optional[int]) -> str:
    """Infer a seniority level from a job title, falling back to years of experience.

    Checks the title (case-insensitive) for keywords in priority order. If no
    keyword matches, falls back to a years-of-experience heuristic. If neither
    is available, defaults to "mid" as a neutral value.

    This is a simple heuristic, not meant to be exhaustive.
    """
    title_lower = (title or "").lower()

    if "principal" in title_lower or "staff" in title_lower:
        return "staff"
    if "senior" in title_lower or "sr." in title_lower:
        return "senior"
    if "junior" in title_lower or "jr." in title_lower or "entry" in title_lower:
        return "entry"
    if (
        "lead" in title_lower
        or "manager" in title_lower
        or "director" in title_lower
        or "head of" in title_lower
    ):
        return "lead"

    if experience_years_min is not None:
        if experience_years_min >= 8:
            return "staff"
        if experience_years_min >= 5:
            return "senior"
        if experience_years_min >= 2:
            return "mid"
        return "entry"

    return "mid"
