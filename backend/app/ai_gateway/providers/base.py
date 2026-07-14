from abc import ABC, abstractmethod
from typing import Any, Optional


class AIProvider(ABC):
    """Base class for AI providers"""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        self.api_key = api_key
        self.config = kwargs
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str = "default",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> str:
        """Generate text response from the provider"""
        pass
    
    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        schema: dict,
        model: str = "default",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> dict:
        """Generate JSON response matching the provided schema"""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging and tracking"""
        pass
    
    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation"""
        return len(text) // 4
