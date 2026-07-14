import json
import logging
from typing import Optional
import anthropic
from .base import AIProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(AIProvider):
    """Anthropic Claude provider"""
    
    MODEL_MAP = {
        "default": "claude-3-5-sonnet-20241022",
        "claude-3-5-sonnet": "claude-3-5-sonnet-20241022",
        "claude-3-haiku": "claude-3-haiku-20240307",
        "fast": "claude-3-haiku-20240307",
        "smart": "claude-3-5-sonnet-20241022",
    }
    
    # Token pricing per million tokens (input, output)
    PRICING = {
        "claude-3-5-sonnet-20241022": (3.0, 15.0),
        "claude-3-haiku-20240307": (0.25, 1.25),
    }
    
    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
    
    @property
    def name(self) -> str:
        return "anthropic"
    
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
        """Generate text response using Claude"""
        resolved_model = self._resolve_model(model)
        
        try:
            response = await self.client.messages.create(
                model=resolved_model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Extract text from response
            text_content = ""
            for block in response.content:
                if block.type == "text":
                    text_content += block.text
            
            # Log usage
            logger.info(
                f"Anthropic API call - model: {resolved_model}, "
                f"input_tokens: {response.usage.input_tokens}, "
                f"output_tokens: {response.usage.output_tokens}"
            )
            
            return text_content
            
        except anthropic.RateLimitError as e:
            logger.error(f"Rate limit exceeded: {e}")
            raise
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
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
        """Generate structured JSON using Claude tool use"""
        resolved_model = self._resolve_model(model)
        
        # Create a tool definition from the schema
        tool = {
            "name": "return_structured_data",
            "description": "Return structured data matching the required schema",
            "input_schema": schema
        }
        
        try:
            response = await self.client.messages.create(
                model=resolved_model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                tools=[tool],
                tool_choice={"type": "tool", "name": "return_structured_data"}
            )
            
            # Extract tool use result
            result = None
            for block in response.content:
                if block.type == "tool_use" and block.name == "return_structured_data":
                    result = block.input
                    break
            
            if result is None:
                raise ValueError("No tool use found in response")
            
            # Log usage (with redaction)
            redacted_result = self._redact_sensitive_data(result)
            logger.info(
                f"Anthropic API call (structured) - model: {resolved_model}, "
                f"input_tokens: {response.usage.input_tokens}, "
                f"output_tokens: {response.usage.output_tokens}, "
                f"result_preview: {str(redacted_result)[:200]}"
            )
            
            return result
            
        except anthropic.RateLimitError as e:
            logger.error(f"Rate limit exceeded: {e}")
            raise
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
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
