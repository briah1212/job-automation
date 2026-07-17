from __future__ import annotations

import json
from typing import Any, Optional

from app.agents.base import BaseAgent
from app.ai_gateway.gateway import AIGateway
from app.ai_gateway.schemas import CoverLetterDraft
from app.models import Application, CanonicalJob, ProfileFact, ResumeVersion

_WORD_LIMIT_TOLERANCE = 1.1

COVER_LETTER_PROMPT_TEMPLATE = """You are drafting a cover letter for a candidate applying to a \
specific job. Write in the candidate's voice, addressed to the hiring team, and follow these \
rules strictly and without exception.

The role being applied for is "{job_title}" at "{company}". Reference this role and company by \
name directly in the letter - do not write a generic letter that could apply to any employer.

You may ONLY draw on the material below - the candidate's resume content and their verified \
profile facts. Never invent employers, job titles, skills, metrics, or achievements that are not \
present in this material.

CANDIDATE RESUME (parsed_data):
{parsed_data}

VERIFIED PROFILE FACTS (id: content):
{profile_facts}

JOB'S STATED NEEDS (requirements and description, use this to decide what to emphasize):
{job_requirements}

JOB DESCRIPTION:
{job_description}

Writing instructions:
- Connect two or three of the candidate's actual experiences (from the resume or verified facts \
above) to the job's actual stated needs. Be specific about what the candidate did and why it \
matters for this role.
- Do not use generic enthusiasm filler such as "I am very excited about this opportunity" or "I \
would be a great fit" unless it is immediately backed up by a concrete, substantive reason.
- Do not simply repeat the resume's bullet points verbatim - synthesize and reframe the material \
in narrative form appropriate to a cover letter.
- {tone_instruction}
- {word_limit_instruction}

Produce the cover letter as structured JSON matching the required schema.
"""

_DEFAULT_WORD_LIMIT_INSTRUCTION = (
    "No specific word limit was given; aim for roughly 250-400 words."
)


class CoverLetterAgent(BaseAgent):
    """Agent that generates a truthfulness-constrained cover letter draft for an application."""

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute cover letter generation. Delegates to `generate`."""
        return await self.generate(
            application=input_data["application"],
            job=input_data["job"],
            resume_version=input_data.get("resume_version"),
            profile_facts=input_data.get("profile_facts", []),
            tone=input_data.get("tone"),
            word_limit=input_data.get("word_limit"),
            user_id=input_data["user_id"],
        )

    async def generate(
        self,
        application: Application,
        job: CanonicalJob,
        resume_version: Optional[ResumeVersion],
        profile_facts: list[ProfileFact],
        tone: Optional[str],
        word_limit: Optional[int],
        user_id: str,
    ) -> dict[str, Any]:
        """Generate a cover letter draft for an application, using only verified source material."""
        parsed_data: dict[str, Any] = (resume_version.parsed_data if resume_version else {}) or {}

        job_requirements = (job.extracted_data or {}).get("requirements", [])

        tone_instruction = (
            f"Write in a {tone} tone throughout the letter."
            if tone
            else "No specific tone was requested; use a natural, professional tone."
        )
        word_limit_instruction = (
            f"Stay under {word_limit} words in total."
            if word_limit
            else _DEFAULT_WORD_LIMIT_INSTRUCTION
        )

        prompt = COVER_LETTER_PROMPT_TEMPLATE.format(
            job_title=job.title,
            company=job.company,
            parsed_data=json.dumps(parsed_data, indent=2, default=str),
            profile_facts=json.dumps(
                [{"id": str(fact.id), "content": fact.content} for fact in profile_facts],
                indent=2,
                default=str,
            ),
            job_requirements=json.dumps(job_requirements, indent=2, default=str),
            job_description=job.description or "",
            tone_instruction=tone_instruction,
            word_limit_instruction=word_limit_instruction,
        )

        result: CoverLetterDraft = await AIGateway().generate_structured(
            prompt=prompt,
            schema=CoverLetterDraft,
            agent_type="cover_letter",
            user_id=user_id,
        )

        warnings: list[str] = list(result.warnings)
        if word_limit and result.word_count > word_limit * _WORD_LIMIT_TOLERANCE:
            warnings.append("Generated content exceeds the requested word limit.")

        claim_provenance = self._build_claim_provenance(result.content, profile_facts)

        return {
            "content": result.content,
            "word_count": result.word_count,
            "warnings": warnings,
            "claim_provenance": claim_provenance,
        }

    @staticmethod
    def _build_claim_provenance(
        content: str, profile_facts: list[ProfileFact]
    ) -> list[dict[str, Any]]:
        """Best-effort mapping of facts referenced in the generated letter back to their source."""
        provenance: list[dict[str, Any]] = []
        content_lower = content.lower()

        for fact in profile_facts:
            fact_content = (fact.content or "").strip()
            if fact_content and fact_content.lower() in content_lower:
                provenance.append(
                    {
                        "profile_fact_id": str(fact.id),
                        "explanation": f"Referenced in cover letter: {fact.content[:60]}",
                    }
                )

        return provenance
