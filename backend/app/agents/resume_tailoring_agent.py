from __future__ import annotations

import json
from typing import Any, Optional
from uuid import UUID

from app.agents.base import BaseAgent
from app.ai_gateway.gateway import AIGateway
from app.ai_gateway.schemas import ResumeTailoring
from app.models import CanonicalJob, DocumentLock, ProfileFact, ResumeVersion
from app.services.requirement_evidence import build_requirement_evidence_matrix

# Lock types that must be enforced by reverting any AI-proposed change back to
# the original value, rather than merely being suggested to the model.
_ENFORCED_LOCK_TYPES = ("exact_title", "exact_dates", "protect_accomplishment")

_FALLBACK_CLAIM_STRENGTH = 0.5

TAILORING_PROMPT_TEMPLATE = """You are tailoring a candidate's resume for a specific job opening. \
Follow these rules strictly and without exception.

ALLOWED changes: reordering sections/bullets, adjusting emphasis, condensing text, rewording for \
clarity, and adding a verified project or accomplishment only if it is directly backed by one of \
the supplied verified facts below.

FORBIDDEN changes: fabricating skills or metrics, changing employment dates, misrepresenting job \
titles or seniority, keyword stuffing, and hidden or invisible text.

You may ONLY use the verified facts listed below as source material for any new or reworded \
content. Never invent information that is not present in these facts or in the original resume.

The following fields are LOCKED by the user and must NOT be altered in any way, under any \
circumstance:
{locked_refs}

ORIGINAL RESUME (parsed_data):
{parsed_data}

REQUIREMENT-EVIDENCE MATRIX (use this to decide what to emphasize and reorder):
{requirement_evidence_matrix}

VERIFIED PROFILE FACTS (id: content):
{profile_facts}

Produce a tailored, truthful version of this resume as structured JSON matching the required \
schema.
"""


class ResumeTailoringAgent(BaseAgent):
    """Agent that tailors a resume to a specific job while enforcing truthfulness and locks."""

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute tailoring logic. Delegates to `tailor`."""
        return await self.tailor(
            resume_version=input_data["resume_version"],
            job=input_data["job"],
            profile_facts=input_data.get("profile_facts", []),
            locks=input_data.get("locks", []),
        )

    async def tailor(
        self,
        resume_version: ResumeVersion,
        job: CanonicalJob,
        profile_facts: list[ProfileFact],
        locks: list[DocumentLock],
    ) -> dict[str, Any]:
        """Tailor a resume version to a job, respecting locks and verified facts only."""
        matrix = build_requirement_evidence_matrix(job, profile_facts)

        original_parsed_data: dict[str, Any] = resume_version.parsed_data or {}
        locked_refs = [lock.target_ref for lock in locks]

        prompt = TAILORING_PROMPT_TEMPLATE.format(
            locked_refs=json.dumps(locked_refs, indent=2),
            parsed_data=json.dumps(original_parsed_data, indent=2, default=str),
            requirement_evidence_matrix=json.dumps(matrix, indent=2, default=str),
            profile_facts=json.dumps(
                [{"id": str(fact.id), "content": fact.content} for fact in profile_facts],
                indent=2,
                default=str,
            ),
        )

        result: ResumeTailoring = await AIGateway().generate_structured(
            prompt=prompt,
            schema=ResumeTailoring,
            agent_type="resume_tailoring",
            user_id=str(resume_version.family_id),
        )

        structured_resume: dict[str, Any] = result.structured_resume
        warnings: list[str] = list(result.warnings)

        enforced_locks = [lock for lock in locks if lock.lock_type in _ENFORCED_LOCK_TYPES]
        if enforced_locks:
            structured_resume, lock_warnings = self._enforce_locks(
                structured_resume, original_parsed_data, enforced_locks, result.changelog
            )
            warnings.extend(lock_warnings)

        claims = self._build_claims(structured_resume, profile_facts, matrix)

        return {
            "structured_resume": structured_resume,
            "requirement_evidence_matrix": matrix,
            "claims": claims,
            "change_log": result.changelog,
            "keyword_coverage": result.keyword_coverage,
            "warnings": warnings,
            "page_count": result.page_count_estimate,
            "quality_score": result.quality_score,
        }

    def _enforce_locks(
        self,
        structured_resume: dict[str, Any],
        original_parsed_data: dict[str, Any],
        enforced_locks: list[DocumentLock],
        changelog: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], list[str]]:
        """Revert any locked field the AI touched back to its original value."""
        warnings: list[str] = []

        changed_refs: set[str] = set()
        for entry in changelog:
            ref = entry.get("target_ref") or entry.get("field") or entry.get("section")
            if ref:
                changed_refs.add(str(ref))

        for lock in enforced_locks:
            target_ref = lock.target_ref
            if target_ref not in changed_refs:
                continue

            original_value = self._get_path_value(original_parsed_data, target_ref)
            if original_value is None:
                continue

            self._set_path_value(structured_resume, target_ref, original_value)
            warnings.append(
                f"Lock '{lock.lock_type}' enforced on '{target_ref}': reverted AI-proposed "
                "change back to the original, verified value."
            )

        return structured_resume, warnings

    @staticmethod
    def _parse_path(path: str) -> list[Any]:
        """Parse a simple dot/bracket path like 'experience[0].title' into tokens."""
        tokens: list[Any] = []
        for part in path.replace("]", "").split("."):
            for sub in part.split("["):
                if sub == "":
                    continue
                tokens.append(int(sub) if sub.isdigit() else sub)
        return tokens

    @classmethod
    def _get_path_value(cls, data: dict[str, Any], path: str) -> Any:
        current: Any = data
        for token in cls._parse_path(path):
            try:
                current = current[token]
            except (KeyError, IndexError, TypeError):
                return None
        return current

    @classmethod
    def _set_path_value(cls, data: dict[str, Any], path: str, value: Any) -> None:
        tokens = cls._parse_path(path)
        if not tokens:
            return

        current: Any = data
        for token in tokens[:-1]:
            try:
                current = current[token]
            except (KeyError, IndexError, TypeError):
                return

        try:
            current[tokens[-1]] = value
        except (TypeError, IndexError):
            return

    def _build_claims(
        self,
        structured_resume: dict[str, Any],
        profile_facts: list[ProfileFact],
        matrix: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Best-effort mapping of resulting resume claims back to supporting facts."""
        claims: list[dict[str, Any]] = []
        fallback_fact_id, fallback_strength = self._best_fact_from_matrix(matrix)

        for section, claim_text in self._iter_claim_texts(structured_resume):
            source_fact_ids: list[str] = []
            strength = 0.0

            for fact in profile_facts:
                content = (fact.content or "").strip()
                if content and content.lower() in claim_text.lower():
                    source_fact_ids.append(str(fact.id))
                    strength = max(strength, self._fact_strength(fact.id, matrix))

            if not source_fact_ids and fallback_fact_id is not None:
                source_fact_ids = [fallback_fact_id]
                strength = fallback_strength

            claims.append(
                {
                    "section": section,
                    "claim_text": claim_text,
                    "source_fact_ids": source_fact_ids,
                    "strength": strength,
                }
            )

        return claims

    @staticmethod
    def _iter_claim_texts(structured_resume: dict[str, Any]):
        summary = structured_resume.get("summary")
        if isinstance(summary, str) and summary.strip():
            yield "summary", summary.strip()

        experience = structured_resume.get("experience")
        if isinstance(experience, list):
            for entry in experience:
                if not isinstance(entry, dict):
                    continue
                for bullet_key in ("achievements", "bullets", "highlights"):
                    bullets = entry.get(bullet_key)
                    if isinstance(bullets, list):
                        for bullet in bullets:
                            if isinstance(bullet, str) and bullet.strip():
                                yield "experience", bullet.strip()
                        break

    @staticmethod
    def _fact_strength(fact_id: UUID, matrix: list[dict[str, Any]]) -> float:
        fact_id_str = str(fact_id)
        for requirement_entry in matrix:
            for evidence in requirement_entry.get("evidence", []):
                if evidence.get("profile_fact_id") == fact_id_str:
                    return float(evidence.get("strength", 0.0))
        return _FALLBACK_CLAIM_STRENGTH

    @staticmethod
    def _best_fact_from_matrix(matrix: list[dict[str, Any]]) -> tuple[Optional[str], float]:
        best_id: Optional[str] = None
        best_strength = 0.0
        for requirement_entry in matrix:
            for evidence in requirement_entry.get("evidence", []):
                strength = float(evidence.get("strength", 0.0))
                if strength > best_strength:
                    best_strength = strength
                    best_id = evidence.get("profile_fact_id")
        return best_id, best_strength
