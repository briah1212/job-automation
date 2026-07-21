import os
import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

_API_URL = os.environ.get("API_URL", "http://api:8000")
_INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")
_TIMEOUT_SECONDS = 30.0


class DynamicQuestionsError(Exception):
    """Raised when the internal dynamic-questions endpoint call fails."""


async def answer_question(user_id: str, question_text: str) -> Dict[str, Any]:
    """Ask the backend to answer a field browser-worker couldn't map on its own.

    Returns the same shape ApplicationQuestionAgent.generate_answer produces:
    answer_text, source, approved, needs_user_input, source_facts. The LLM
    call (if any) happens entirely on the backend side - browser-worker never
    talks to the AI gateway directly, and this answer only ever fills a form
    field, never decides whether to submit.
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
        try:
            response = await client.post(
                f"{_API_URL}/api/internal/dynamic-questions/answer",
                headers={"X-Internal-Api-Key": _INTERNAL_API_KEY},
                json={"user_id": user_id, "question_text": question_text},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            logger.error("Dynamic question answer failed: %s - %s", exc.response.status_code, exc.response.text)
            raise DynamicQuestionsError(f"answer failed: {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            logger.error("Dynamic question request error: %s", exc)
            raise DynamicQuestionsError(f"answer request error: {exc}") from exc
