from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base


class ModelCall(Base):
    """AI model call tracking for cost and usage analytics."""
    
    __tablename__ = "model_calls"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id = Column(String, nullable=False, index=True)
    
    # Provider and model info
    provider = Column(String, nullable=False, index=True)
    model = Column(String, nullable=False, index=True)
    
    # Agent and user tracking
    agent_type = Column(String, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Token usage
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    
    # Cost in USD
    cost_usd = Column(Float, nullable=False)
    
    # Additional metadata
    call_metadata = Column(JSONB, default=dict, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
