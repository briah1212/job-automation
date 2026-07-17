from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class DocumentRenderingBase(BaseModel):
    """Base document rendering schema."""
    format: str
    file_path: str
    page_count: Optional[int] = None


class DocumentRenderingCreate(DocumentRenderingBase):
    """Document rendering creation schema."""
    resume_version_id: UUID


class DocumentRendering(DocumentRenderingBase):
    """Document rendering response schema."""
    id: UUID
    resume_version_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}
