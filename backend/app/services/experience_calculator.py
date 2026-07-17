from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List

from app.models import ProfileFact

_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_MONTH_ALTERNATION = "|".join(sorted(_MONTHS.keys(), key=len, reverse=True))

# Best-effort regex for date ranges like "2018-2022", "2018-Present",
# "January 2018 - March 2022", "Jan 2018 - Present". Not a full NLP date parser.
_DATE_RANGE_RE = re.compile(
    rf"""
    (?:(?P<start_month>{_MONTH_ALTERNATION})\.?\s+)?
    (?P<start_year>(?:19|20)\d{{2}})
    \s*(?:-|–|to)\s*
    (?:(?P<end_month>{_MONTH_ALTERNATION})\.?\s+)?
    (?P<end_year>(?:19|20)\d{{2}}|present|current)
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _month_index(year: int, month: int) -> int:
    """Convert a (year, month) pair into an absolute month index for arithmetic."""
    return year * 12 + (month - 1)


def _extract_date_ranges(text: str) -> List[Dict[str, Any]]:
    """Extract best-effort date ranges from free text.

    Returns a list of dicts with the matched text and start/end month indices.
    """
    ranges: List[Dict[str, Any]] = []
    if not text:
        return ranges

    today = date.today()

    for match in _DATE_RANGE_RE.finditer(text):
        start_year = int(match.group("start_year"))
        start_month_name = match.group("start_month")
        start_month = _MONTHS.get(start_month_name.lower(), 1) if start_month_name else 1

        end_year_raw = match.group("end_year")
        if end_year_raw.lower() in ("present", "current"):
            end_year = today.year
            end_month = today.month
        else:
            end_year = int(end_year_raw)
            end_month_name = match.group("end_month")
            # When only a year is given (no month), treat the end as the start of that
            # year so a bare "YYYY-YYYY" range yields a clean year-count difference.
            end_month = _MONTHS.get(end_month_name.lower(), 1) if end_month_name else 1

        start_idx = _month_index(start_year, start_month)
        end_idx = _month_index(end_year, end_month)

        if end_idx < start_idx:
            continue

        ranges.append(
            {
                "text": match.group(0).strip(),
                "start_idx": start_idx,
                "end_idx": end_idx,
            }
        )

    return ranges


def _merge_and_sum_months(intervals: List[tuple[int, int]]) -> int:
    """Merge overlapping [start, end] month-index intervals and sum total months covered."""
    if not intervals:
        return 0

    sorted_intervals = sorted(intervals, key=lambda pair: pair[0])
    merged: List[list[int]] = [list(sorted_intervals[0])]

    for start, end in sorted_intervals[1:]:
        last = merged[-1]
        if start <= last[1]:
            last[1] = max(last[1], end)
        else:
            merged.append([start, end])

    return sum(end - start for start, end in merged)


def calculate_years_of_experience(
    profile_facts: List[ProfileFact], skill: str, policy: str = "non_overlapping"
) -> Dict[str, Any]:
    """Calculate years of experience with a given skill from a user's profile facts.

    Filters profile_facts to fact_type == "experience_bullet" whose content mentions
    `skill` (case-insensitive; an empty skill matches any experience_bullet). Attempts
    best-effort date-range extraction from each matching fact's content/original_text.

    Never guesses: if no date ranges can be extracted from any matching fact, returns
    years=None with a warning requiring user input.
    """
    skill_lower = skill.lower().strip()

    matching_facts = [
        fact
        for fact in profile_facts
        if fact.fact_type == "experience_bullet"
        and (not skill_lower or skill_lower in (fact.content or "").lower())
    ]

    calculation_basis: List[Dict[str, Any]] = []
    intervals: List[tuple[int, int]] = []
    all_indices: List[int] = []

    for fact in matching_facts:
        text_sources = [fact.content or "", fact.original_text or ""]
        extracted_ranges: List[Dict[str, Any]] = []
        for text in text_sources:
            extracted_ranges.extend(_extract_date_ranges(text))

        if not extracted_ranges:
            continue

        for date_range in extracted_ranges:
            calculation_basis.append(
                {
                    "fact_id": str(fact.id) if fact.id else None,
                    "content": fact.content,
                    "extracted_range": date_range["text"],
                }
            )
            intervals.append((date_range["start_idx"], date_range["end_idx"]))
            all_indices.append(date_range["start_idx"])
            all_indices.append(date_range["end_idx"])

    if not intervals:
        return {
            "years": None,
            "calculation_basis": [],
            "warning": "Insufficient date information to calculate years of experience; user input required.",
            "policy": policy,
        }

    if policy == "calendar_duration":
        total_months = max(all_indices) - min(all_indices)
    else:  # non_overlapping (default)
        total_months = _merge_and_sum_months(intervals)

    years = round(total_months / 12, 1)

    return {
        "years": years,
        "calculation_basis": calculation_basis,
        "policy": policy,
    }
