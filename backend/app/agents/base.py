from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """Base class for all agents."""
    
    @abstractmethod
    def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent logic."""
        pass
