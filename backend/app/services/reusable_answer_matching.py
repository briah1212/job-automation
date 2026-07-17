from __future__ import annotations

import re
from typing import List, Optional

from app.models import ReusableAnswer


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, and collapse whitespace for comparison."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def find_matching_reusable_answer(
    question_text: str, reusable_answers: List[ReusableAnswer]
) -> Optional[ReusableAnswer]:
    """Find a reusable answer whose canonical question or semantic variants match `question_text`.

    This is deterministic normalized-string matching, not ML - real semantic matching
    (e.g. embeddings) could replace this later.

    Prefers user_approved=True matches; only falls back to unapproved matches if no
    approved match exists.
    """
    normalized_question = _normalize(question_text)

    approved = [a for a in reusable_answers if a.user_approved]
    unapproved = [a for a in reusable_answers if not a.user_approved]

    for candidates in (approved, unapproved):
        # First pass: exact canonical_question match
        for answer in candidates:
            if _normalize(answer.canonical_question) == normalized_question:
                return answer

        # Second pass: semantic_variants match
        for answer in candidates:
            for variant in answer.semantic_variants or []:
                if _normalize(variant) == normalized_question:
                    return answer

    return None
