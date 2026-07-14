import json
import logging
from typing import Optional
import openai
from .base import AIProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    """OpenAI GPT provider"""
    
    MODEL_MAP = {
        "default": "gpt-4-turbo-preview",
        "gpt-4": "gpt-4-turbo-preview",
        "gpt-3.5": "gpt-3.5-turbo",
        "fast": "gpt-3.5-turbo",
        "smart": "gpt-4-turbo-preview",
    }
    
    # Token pricing per million tokens (input, output)
    PRICING = {
        "gpt-4-turbo-preview": (10.0, 30.0),
        "gpt-3.5-turbo": (0.5, 1.5),
    }
    
    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        self.client = openai.AsyncOpenAI(api_key=api_key)
    
    @property
    def name(self) -> str:
        return "openai"
    
    def _resolve_model(self, model: str) -> str:
        """Resolve model alias to actual model name"""
        return self.MODEL_MAP.get(model, model)
    
    def _redact_sensitive_data(self, data: dict) -> dict:
        """Redact sensitive fields from logs"""
        redacted = data.copy()
        sensitive_fields = ["email", "phone", "address", "ssn", "api_key"]
        
        for field in sensitive_fields:
            if field in redacted:
                redacted[field] = "[REDACTED]"
        
        # Recursively redact nested dicts and lists
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
        """Generate text response using GPT"""
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
            
            # Log usage
            logger.info(
                f"OpenAI API call - model: {resolved_model}, "
                f"input_tokens: {response.usage.prompt_tokens}, "
                f"output_tokens: {response.usage.completion_tokens}"
            )
            
            return text_content
            
        except openai.RateLimitError as e:
            logger.error(f"Rate limit exceeded: {e}")
            raise
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
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
        """Generate structured JSON using GPT JSON mode"""
        resolved_model = self._resolve_model(model)
        
        # Enhance prompt with schema information
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
            
            # Log usage (with redaction)
            redacted_result = self._redact_sensitive_data(result)
            logger.info(
                f"OpenAI API call (structured) - model: {resolved_model}, "
                f"input_tokens: {response.usage.prompt_tokens}, "
                f"output_tokens: {response.usage.completion_tokens}, "
                f"result_preview: {str(redacted_result)[:200]}"
            )
            
            return result
            
        except openai.RateLimitError as e:
            logger.error(f"Rate limit exceeded: {e}")
            raise
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise
    
    def calculate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Calculate cost for a request"""
        resolved_model = self._resolve_model(model)
        if resolved_model not in self.PRICING:
            logger.warning(f"Unknown model for pricing: {resolved_model}")
            return 0.0
        
        input_price, output_price = self.PRICING[resolved_model]
        cost = (input_tokens / 1_000_000 * input_price) + (output_tokens / 1_000_000 * output_price)
        return cost
