from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProfileFactBase(BaseModel):
    """Base profile fact schema."""
    fact_type: str
    content: str

    source_type: str
    source_identifier: Optional[str] = None
    original_text: Optional[str] = None

    confidence: float = 1.0
    user_verified: bool = False

    permitted_uses: List[str] = Field(default_factory=list)


class ProfileFactCreate(ProfileFactBase):
    """Profile fact creation schema."""
    pass


class ProfileFact(ProfileFactBase):
    """Profile fact response schema."""
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
