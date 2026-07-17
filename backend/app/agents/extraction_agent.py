from __future__ import annotations

from typing import Any, Optional

from app.agents.base import BaseAgent
from app.ai_gateway.gateway import AIGateway
from app.ai_gateway.schemas import ExtractedJob

# Truncate raw posting text before including it in the prompt so we don't blow up
# token usage/prompt size on huge pages.
_MAX_RAW_TEXT_CHARS = 8000


class ExtractionAgent(BaseAgent):
    """Agent for extracting structured job data from raw job posting text."""

    def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute agent logic (sync wrapper is not used - callers should await extract)."""
        raise NotImplementedError(
            "ExtractionAgent is async-only; call extract() directly."
        )

    async def extract(
        self,
        raw_text: str,
        source_url: Optional[str],
        user_id: str,
    ) -> dict[str, Any]:
        """Extract structured job data (company, title, skills, etc.) from raw posting text."""
        truncated_text = (raw_text or "")[:_MAX_RAW_TEXT_CHARS]

        prompt = (
            "Extract structured job posting data from the following raw job posting "
            "text. Identify the company name, job title, location, remote policy, "
            "salary range, required skills, preferred skills, responsibilities, and "
            "minimum years of experience required.\n\n"
        )
        if source_url:
            prompt += f"Source URL: {source_url}\n\n"
        prompt += f"Raw job posting text:\n{truncated_text}"

        result: ExtractedJob = await AIGateway().generate_structured(
            prompt=prompt,
            schema=ExtractedJob,
            agent_type="job_extraction",
            user_id=user_id,
        )

        return result.model_dump()
