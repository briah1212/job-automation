import json
import logging
from typing import Optional
import openai
from .base import AIProvider

logger = logging.getLogger(__name__)


class DeepSeekProvider(AIProvider):
    """DeepSeek provider - OpenAI-API-compatible, different base_url/models/pricing."""

    MODEL_MAP = {
        "default": "deepseek-chat",
        "fast": "deepseek-chat",
        "smart": "deepseek-reasoner",
        "reasoner": "deepseek-reasoner",
    }

    # Approximate published per-million-token pricing (cache-miss rates) -
    # only used for internal cost-tracking estimates, not billing.
    PRICING = {
        "deepseek-chat": (0.27, 1.10),
        "deepseek-reasoner": (0.55, 2.19),
    }

    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        self.client = openai.AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    @property
    def name(self) -> str:
        return "deepseek"

    def _resolve_model(self, model: str) -> str:
        return self.MODEL_MAP.get(model, model)

    def _redact_sensitive_data(self, data: dict) -> dict:
        redacted = data.copy()
        sensitive_fields = ["email", "phone", "address", "ssn", "api_key"]

        for field in sensitive_fields:
            if field in redacted:
                redacted[field] = "[REDACTED]"

        for key, value in redacted.items():
            if isinstance(value, dict):
                redacted[key] = self._redact_sensitive_data(value)
            elif isinstance(value, list):
                redacted[key] = [
                    self._redact_sensitive_data(item) if isinstance(item, dict) else item
                    for item in value
                ]

        return redacted

    async def generate(
        self,
        prompt: str,
        model: str = "default",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> str:
        resolved_model = self._resolve_model(model)

        try:
            response = await self.client.chat.completions.create(
                model=resolved_model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            text_content = response.choices[0].message.content

            logger.info(
                f"DeepSeek API call - model: {resolved_model}, "
                f"input_tokens: {response.usage.prompt_tokens}, "
                f"output_tokens: {response.usage.completion_tokens}"
            )

            return text_content

        except openai.RateLimitError as e:
            logger.error(f"Rate limit exceeded: {e}")
            raise
        except openai.APIError as e:
            logger.error(f"DeepSeek API error: {e}")
            raise

    async def generate_json(
        self,
        prompt: str,
        schema: dict,
        model: str = "default",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> dict:
        resolved_model = self._resolve_model(model)

        enhanced_prompt = f"""{prompt}

Return a JSON object matching this schema:
{json.dumps(schema, indent=2)}

Respond with valid JSON only."""

        try:
            response = await self.client.chat.completions.create(
                model=resolved_model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "user", "content": enhanced_prompt}
                ],
                response_format={"type": "json_object"}
            )

            text_content = response.choices[0].message.content
            result = json.loads(text_content)

            redacted_result = self._redact_sensitive_data(result)
            logger.info(
                f"DeepSeek API call (structured) - model: {resolved_model}, "
                f"input_tokens: {response.usage.prompt_tokens}, "
                f"output_tokens: {response.usage.completion_tokens}, "
                f"result_preview: {str(redacted_result)[:200]}"
            )

            return result

        except openai.RateLimitError as e:
            logger.error(f"Rate limit exceeded: {e}")
            raise
        except openai.APIError as e:
            logger.error(f"DeepSeek API error: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise

    def calculate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        resolved_model = self._resolve_model(model)
        if resolved_model not in self.PRICING:
            logger.warning(f"Unknown model for pricing: {resolved_model}")
            return 0.0

        input_price, output_price = self.PRICING[resolved_model]
        cost = (input_tokens / 1_000_000 * input_price) + (output_tokens / 1_000_000 * output_price)
        return cost
