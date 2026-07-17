from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.ai_gateway.gateway import AIGateway
from app.ai_gateway.schemas import JobClassification


class ClassificationAgent(BaseAgent):
    """Agent for classifying a job posting into a primary/secondary category."""

    def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute agent logic (sync wrapper is not used - callers should await classify)."""
        raise NotImplementedError(
            "ClassificationAgent is async-only; call classify() directly."
        )

    async def classify(
        self,
        title: str,
        responsibilities: list[str],
        user_id: str,
    ) -> dict[str, Any]:
        """Classify a job into a primary category (plus secondary categories) based on title and responsibilities."""
        responsibilities_text = "\n".join(f"- {item}" for item in responsibilities) or "(none provided)"

        prompt = (
            "Classify the following job posting into a primary category (e.g. "
            "software_engineering, data_engineering, machine_learning, product_management, "
            "etc.), along with any relevant secondary categories.\n\n"
            f"Job title: {title}\n\n"
            f"Responsibilities:\n{responsibilities_text}"
        )

        result: JobClassification = await AIGateway().generate_structured(
            prompt=prompt,
            schema=JobClassification,
            agent_type="job_classification",
            user_id=user_id,
        )

        return result.model_dump()
