from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from app.agents.base import BaseAgent
from app.ai_gateway.gateway import AIGateway
from app.ai_gateway.schemas import ReviewResult
from app.models import Application, CanonicalJob, ResumeVersion

# Case-insensitive substring markers that indicate unfinished/placeholder content.
PLACEHOLDER_MARKERS = ["TODO", "LOREM IPSUM", "[INSERT", "XXX", "PLACEHOLDER"]

# Loose date-like patterns worth double-checking for validity (not full ISO validation,
# just enough to catch the common "13/45/2024" style typos before they reach a real form).
_DATE_PATTERN = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b")

# Very loose heuristic: "company"/"position" followed by a run of capitalized words. This is
# intentionally permissive - false positives are fine here since a mismatch is only ever
# surfaced as a warning, never a blocking finding.
_COMPANY_MENTION_PATTERN = re.compile(
    r"\b(?:company|position)\s+([A-Z][\w&.,'-]*(?:\s+[A-Z][\w&.,'-]*)*)"
)

REVIEW_PROMPT_TEMPLATE = """You are an independent auditor reviewing a job application for errors before it is submitted on the candidate's behalf. You did not write any of this content - your only job is to catch mistakes a careless applicant might miss, especially claims that are not supported by the candidate's actual background.

Job being applied to:
- Title: {title}
- Company: {company}

Candidate resume summary on file:
{resume_summary}

Application questions and the answers that will be submitted:
{qa_lines}

Carefully audit the answers above. Flag anything that:
- Makes a factual or experience claim that is not plausibly supported by the resume summary.
- Reads as generic, evasive, or clearly copy-pasted from a different application.
- Contains an internal contradiction (e.g. conflicting dates, titles, or employers).
- Would embarrass the candidate if a hiring manager noticed it.

Return blocking_findings for issues serious enough that this application should NOT be submitted as-is, and warnings for issues worth a second look but not disqualifying. Set passed to false if there are any blocking_findings. Set confidence to your confidence in this assessment, from 0.0 to 1.0."""


class ApplicationReviewAgent(BaseAgent):
    """Independent, pre-submission compliance review of a job application.

    Runs a set of fast deterministic structural checks first (missing resume, unanswered
    high-risk questions, placeholder text, malformed dates, wrong-company mentions, duplicate
    applications), then supplements those with an AI-assisted pass over the free-text answers
    to catch unsupported claims. This agent is deliberately independent from any
    content-generation agent: it uses its own prompt and, in production, may be configured to
    a different model than the one used to draft the answers being reviewed.
    """

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute the review. Expects input_data with keys:
        application, job, resume_version (optional), questions_and_answers (list[dict]),
        and optionally is_duplicate (bool).
        """
        return await self.review(
            application=input_data["application"],
            job=input_data["job"],
            resume_version=input_data.get("resume_version"),
            questions_and_answers=input_data.get("questions_and_answers", []),
            is_duplicate=input_data.get("is_duplicate", False),
        )

    async def review(
        self,
        application: Application,
        job: CanonicalJob,
        resume_version: Optional[ResumeVersion],
        questions_and_answers: list[dict],
        is_duplicate: bool = False,
    ) -> dict[str, Any]:
        """Run the full review pipeline.

        Note on the duplicate-application check: rather than accepting a `db: Session` here
        (which would couple this agent to the ORM/session lifecycle), the caller (the
        auto-review route) is expected to perform that query itself and pass the boolean
        result in via `is_duplicate`. This keeps the agent trivially unit-testable without a
        database.
        """
        blocking_findings: list[str] = []
        warnings: list[str] = []

        # 1. Resume must be attached.
        if resume_version is None:
            blocking_findings.append("No resume selected for this application.")

        # 2. No unanswered high-risk questions.
        for qa in questions_and_answers:
            answer_text = (qa.get("answer_text") or "").strip()
            answered = bool(qa.get("answered")) and bool(answer_text)
            if qa.get("risk_level") == "high" and not answered:
                blocking_findings.append(
                    f"Unanswered high-risk question: \"{qa.get('question_text', '')}\""
                )

        # 3. No placeholder text.
        for qa in questions_and_answers:
            answer_text = qa.get("answer_text") or ""
            upper_text = answer_text.upper()
            for marker in PLACEHOLDER_MARKERS:
                if marker in upper_text:
                    blocking_findings.append(
                        f"Placeholder text ('{marker}') found in answer to "
                        f"\"{qa.get('question_text', '')}\"."
                    )
                    break

        # 4. No wrong company name in generated content (warning only - heuristic is loose).
        for qa in questions_and_answers:
            answer_text = qa.get("answer_text") or ""
            for match in _COMPANY_MENTION_PATTERN.finditer(answer_text):
                mentioned = match.group(1).strip()
                job_company = (job.company or "").strip()
                if not mentioned or not job_company:
                    continue
                if job_company.lower() in mentioned.lower() or mentioned.lower() in job_company.lower():
                    continue
                warnings.append(
                    f"Answer to \"{qa.get('question_text', '')}\" may reference the wrong "
                    f"company ('{mentioned}' vs expected '{job_company}')."
                )
                break

        # 5. No malformed dates (warning only).
        for qa in questions_and_answers:
            answer_text = qa.get("answer_text") or ""
            for match in _DATE_PATTERN.finditer(answer_text):
                date_str = match.group(0)
                if not self._is_valid_date(date_str):
                    warnings.append(
                        f"Possible malformed date '{date_str}' found in answer to "
                        f"\"{qa.get('question_text', '')}\"."
                    )

        # 6. No duplicate application.
        if is_duplicate:
            blocking_findings.append(
                "A non-draft application already exists for this user and job."
            )

        # 7. AI-assisted pass over free-text answers for unsupported claims, etc.
        resume_summary = "(no resume attached)"
        if resume_version is not None:
            parsed = resume_version.parsed_data or {}
            resume_summary = str(parsed.get("summary") or parsed)[:1500]

        qa_lines = "\n".join(
            f"- Q: {qa.get('question_text', '')}\n  A: {qa.get('answer_text') or '(no answer)'}"
            for qa in questions_and_answers
        ) or "(no questions on file)"

        prompt = REVIEW_PROMPT_TEMPLATE.format(
            title=job.title,
            company=job.company,
            resume_summary=resume_summary,
            qa_lines=qa_lines,
        )

        try:
            ai_result = await AIGateway().generate_structured(
                prompt=prompt,
                schema=ReviewResult,
                agent_type="application_review",
                user_id=str(application.user_id),
            )
            for finding in ai_result.blocking_findings:
                if finding not in blocking_findings:
                    blocking_findings.append(finding)
            for warning in ai_result.warnings:
                if warning not in warnings:
                    warnings.append(warning)
        except Exception:
            # The AI pass is a supplementary signal on top of the deterministic checks above;
            # if it fails we still return the deterministic result rather than blocking review.
            warnings.append(
                "Automated AI content review could not be completed; only structural checks were run."
            )

        passed = len(blocking_findings) == 0
        confidence = 1.0 - (0.15 * len(warnings)) - (0.4 * len(blocking_findings))
        confidence = max(0.0, min(1.0, confidence))

        recommended_correction = None
        if blocking_findings:
            recommended_correction = f"Resolve first: {blocking_findings[0]}"

        return {
            "passed": passed,
            "blocking_findings": blocking_findings,
            "warnings": warnings,
            "confidence": confidence,
            "recommended_correction": recommended_correction,
        }

    @staticmethod
    def _is_valid_date(date_str: str) -> bool:
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
            try:
                datetime.strptime(date_str, fmt)
                return True
            except ValueError:
                continue
        return False
