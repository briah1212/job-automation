from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class DocumentLockBase(BaseModel):
    """Base document lock schema."""
    lock_type: str
    target_ref: str
    value: Optional[Any] = None


class DocumentLockCreate(DocumentLockBase):
    """Document lock creation schema."""
    resume_family_id: UUID


class DocumentLock(DocumentLockBase):
    """Document lock response schema."""
    id: UUID
    resume_family_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}
