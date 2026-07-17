"""Compute a human-reviewable diff between two resume versions' parsed data."""
from __future__ import annotations

import difflib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.models.resume import ResumeVersion


def _experience_label(item: Any) -> str:
    """Produce a comparable/display label for an experience entry."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        parts = [
            item.get("title") or item.get("role"),
            item.get("company"),
            item.get("dates") or item.get("date_range"),
        ]
        label = " - ".join(p for p in parts if p)
        return label or str(item)
    return str(item)


def _diff_summary(before: str, after: str) -> dict:
    """Word-level diff of the summary/objective text."""
    before_words = before.split()
    after_words = after.split()

    diff_lines = list(difflib.ndiff(before_words, after_words))

    return {
        "before": before,
        "after": after,
        "diff_lines": diff_lines,
    }


def _diff_skills(before: list, after: list) -> dict:
    """Set difference plus reorder detection for the skills list."""
    before_norm = [str(s) for s in (before or [])]
    after_norm = [str(s) for s in (after or [])]

    before_set = set(before_norm)
    after_set = set(after_norm)

    added = [s for s in after_norm if s not in before_set]
    removed = [s for s in before_norm if s not in after_set]

    reordered: list[str] = []
    if before_set == after_set and before_norm != after_norm:
        reordered = after_norm

    return {
        "added": added,
        "removed": removed,
        "reordered": reordered,
    }


def _diff_experience(before: list, after: list) -> dict:
    """Coarse per-item comparison of the experience section."""
    before_labels = [_experience_label(i) for i in (before or [])]
    after_labels = [_experience_label(i) for i in (after or [])]

    before_set = set(before_labels)
    after_set = set(after_labels)

    added = [label for label in after_labels if label not in before_set]
    removed = [label for label in before_labels if label not in after_set]

    reordered: list[str] = []
    if before_set == after_set and before_labels != after_labels:
        reordered = after_labels

    return {
        "added": added,
        "removed": removed,
        "reordered": reordered,
    }


def compute_resume_diff(base_version: "ResumeVersion", new_version: "ResumeVersion") -> dict:
    """Compare two resume versions' `parsed_data` and return a human-reviewable diff.

    The result is best-effort and intended for a human reviewer (the diff
    viewer described in spec.md section 7), not a precise AST-level diff.
    """
    base_data: dict = base_version.parsed_data or {}
    new_data: dict = new_version.parsed_data or {}

    warnings: list[str] = []

    summary_change = _diff_summary(
        str(base_data.get("summary", "")),
        str(new_data.get("summary", "")),
    )

    skills_change = _diff_skills(base_data.get("skills", []), new_data.get("skills", []))

    experience_change = _diff_experience(
        base_data.get("experience", []), new_data.get("experience", [])
    )

    added: list[str] = list(skills_change["added"]) + list(experience_change["added"])
    removed: list[str] = list(skills_change["removed"]) + list(experience_change["removed"])
    reordered: list[str] = list(skills_change["reordered"]) + list(experience_change["reordered"])

    keyword_changes = {
        "added": skills_change["added"],
        "removed": skills_change["removed"],
    }

    # Best-effort coverage check: warn about fields present in one version's
    # parsed_data but missing entirely from the other.
    base_keys = set(base_data.keys())
    new_keys = set(new_data.keys())
    for key in sorted(base_keys - new_keys):
        warnings.append(f"Field '{key}' present in base version but missing in new version")
    for key in sorted(new_keys - base_keys):
        warnings.append(f"Field '{key}' present in new version but missing in base version")

    return {
        "added": added,
        "removed": removed,
        "reordered": reordered,
        "keyword_changes": keyword_changes,
        "summary_change": summary_change,
        "skills_change": skills_change,
        "experience_change": experience_change,
        "warnings": warnings,
    }
