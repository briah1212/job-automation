import logging
import os
import uuid
from typing import Type, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from .providers import AIProvider, MockProvider, AnthropicProvider, OpenAIProvider, DeepSeekProvider
from .cost_tracker import CostTracker

logger = logging.getLogger(__name__)


class AIGateway:
    """Provider-independent AI gateway with cost tracking and mock mode"""
    
    def __init__(
        self,
        provider: Optional[str] = None,
        db_session: Optional[AsyncSession] = None,
        api_key: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize AI Gateway
        
        Args:
            provider: Provider name (mock, anthropic, openai) or None for auto-detect
            db_session: Database session for cost tracking
            api_key: API key for the provider (or use env vars)
            **kwargs: Additional provider configuration
        """
        self.db_session = db_session
        self.cost_tracker = CostTracker(db_session)
        
        # Determine provider
        if provider is None:
            provider = os.getenv("AI_PROVIDER", "mock")
        
        # Initialize provider
        self.provider = self._create_provider(provider, api_key, **kwargs)
        logger.info(f"Initialized AI Gateway with provider: {self.provider.name}")
    
    def _create_provider(
        self,
        provider_name: str,
        api_key: Optional[str] = None,
        **kwargs
    ) -> AIProvider:
        """Create provider instance"""
        provider_name = provider_name.lower()
        
        if provider_name == "mock":
            return MockProvider(**kwargs)
        
        elif provider_name == "anthropic":
            api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                logger.warning("No Anthropic API key found, falling back to mock provider")
                return MockProvider(**kwargs)
            return AnthropicProvider(api_key=api_key, **kwargs)
        
        elif provider_name == "openai":
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.warning("No OpenAI API key found, falling back to mock provider")
                return MockProvider(**kwargs)
            return OpenAIProvider(api_key=api_key, **kwargs)

        elif provider_name == "deepseek":
            api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
            if not api_key:
                logger.warning("No DeepSeek API key found, falling back to mock provider")
                return MockProvider(**kwargs)
            return DeepSeekProvider(api_key=api_key, **kwargs)

        else:
            logger.error(f"Unknown provider: {provider_name}, falling back to mock")
            return MockProvider(**kwargs)
    
    async def generate_text(
        self,
        prompt: str,
        model: str = "default",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        agent_type: str = "unknown",
        user_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Generate text response
        
        Args:
            prompt: Input prompt
            model: Model name or alias
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            agent_type: Type of agent making the request (for tracking)
            user_id: User ID (for tracking)
            **kwargs: Additional provider-specific options
        
        Returns:
            Generated text
        """
        trace_id = str(uuid.uuid4())
        
        try:
            logger.info(f"[{trace_id}] Generating text with {self.provider.name}")
            
            result = await self.provider.generate(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            # Track cost (estimate tokens for mock provider)
            input_tokens = self.provider.estimate_tokens(prompt)
            output_tokens = self.provider.estimate_tokens(result)
            
            cost = 0.0
            if hasattr(self.provider, 'calculate_cost'):
                cost = self.provider.calculate_cost(input_tokens, output_tokens, model)
            
            await self.cost_tracker.track_call(
                provider_name=self.provider.name,
                model=model,
                agent_type=agent_type,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                trace_id=trace_id,
                user_id=user_id,
                metadata={"type": "text_generation"}
            )
            
            return result
            
        except Exception as e:
            logger.error(f"[{trace_id}] Text generation failed: {e}")
            raise
    
    async def generate_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
        model: str = "default",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        agent_type: str = "unknown",
        user_id: Optional[str] = None,
        **kwargs
    ) -> BaseModel:
        """
        Generate structured JSON output matching the schema
        
        Args:
            prompt: Input prompt
            schema: Pydantic model class for the output schema
            model: Model name or alias
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            agent_type: Type of agent making the request (for tracking)
            user_id: User ID (for tracking)
            **kwargs: Additional provider-specific options
        
        Returns:
            Validated Pydantic model instance
        """
        trace_id = str(uuid.uuid4())
        
        try:
            logger.info(f"[{trace_id}] Generating structured output with {self.provider.name}")
            
            # Convert Pydantic schema to JSON schema
            json_schema = schema.model_json_schema()
            
            result_dict = await self.provider.generate_json(
                prompt=prompt,
                schema=json_schema,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            # Validate against Pydantic schema
            result = schema.model_validate(result_dict)
            
            # Track cost
            input_tokens = self.provider.estimate_tokens(prompt)
            output_tokens = self.provider.estimate_tokens(str(result_dict))
            
            cost = 0.0
            if hasattr(self.provider, 'calculate_cost'):
                cost = self.provider.calculate_cost(input_tokens, output_tokens, model)
            
            await self.cost_tracker.track_call(
                provider_name=self.provider.name,
                model=model,
                agent_type=agent_type,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                trace_id=trace_id,
                user_id=user_id,
                metadata={
                    "type": "structured_generation",
                    "schema": schema.__name__
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"[{trace_id}] Structured generation failed: {e}")
            raise
    
    async def get_usage_stats(
        self,
        user_id: Optional[str] = None,
        agent_type: Optional[str] = None
    ) -> dict:
        """Get usage statistics"""
        return await self.cost_tracker.get_usage_stats(
            user_id=user_id,
            agent_type=agent_type
        )
    
    async def get_usage_by_agent(self, user_id: Optional[str] = None) -> list[dict]:
        """Get usage broken down by agent type"""
        return await self.cost_tracker.get_usage_by_agent(user_id=user_id)
