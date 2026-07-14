import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)


class CostTracker:
    """Track AI usage costs and store in database"""
    
    def __init__(self, db_session: Optional[AsyncSession] = None):
        self.db_session = db_session
    
    async def track_call(
        self,
        provider_name: str,
        model: str,
        agent_type: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        trace_id: str,
        user_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        """Track an AI call in the database"""
        if self.db_session is None:
            logger.warning("No database session provided, skipping cost tracking")
            return
        
        try:
            # Import here to avoid circular dependency
            from app.models import ModelCall
            
            call = ModelCall(
                trace_id=trace_id,
                provider=provider_name,
                model=model,
                agent_type=agent_type,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                user_id=user_id,
                metadata=metadata or {},
                created_at=datetime.utcnow()
            )
            
            self.db_session.add(call)
            await self.db_session.flush()
            
            logger.info(
                f"Tracked AI call - trace_id: {trace_id}, "
                f"provider: {provider_name}, model: {model}, "
                f"tokens: {input_tokens + output_tokens}, cost: ${cost:.6f}"
            )
            
        except Exception as e:
            logger.error(f"Failed to track AI call: {e}")
            # Don't raise - tracking failure shouldn't break the main flow
    
    async def get_usage_stats(
        self,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        agent_type: Optional[str] = None
    ) -> dict:
        """Get aggregated usage statistics"""
        if self.db_session is None:
            logger.warning("No database session provided")
            return {}
        
        try:
            from app.models import ModelCall
            from sqlalchemy import func
            
            query = select(
                func.count(ModelCall.id).label("call_count"),
                func.sum(ModelCall.input_tokens).label("total_input_tokens"),
                func.sum(ModelCall.output_tokens).label("total_output_tokens"),
                func.sum(ModelCall.cost_usd).label("total_cost")
            )
            
            if user_id:
                query = query.where(ModelCall.user_id == user_id)
            if start_date:
                query = query.where(ModelCall.created_at >= start_date)
            if end_date:
                query = query.where(ModelCall.created_at <= end_date)
            if agent_type:
                query = query.where(ModelCall.agent_type == agent_type)
            
            result = await self.db_session.execute(query)
            row = result.first()
            
            return {
                "call_count": row.call_count or 0,
                "total_input_tokens": row.total_input_tokens or 0,
                "total_output_tokens": row.total_output_tokens or 0,
                "total_tokens": (row.total_input_tokens or 0) + (row.total_output_tokens or 0),
                "total_cost_usd": float(row.total_cost or 0)
            }
            
        except Exception as e:
            logger.error(f"Failed to get usage stats: {e}")
            return {}
    
    async def get_usage_by_agent(
        self,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> list[dict]:
        """Get usage broken down by agent type"""
        if self.db_session is None:
            logger.warning("No database session provided")
            return []
        
        try:
            from app.models import ModelCall
            from sqlalchemy import func
            
            query = select(
                ModelCall.agent_type,
                func.count(ModelCall.id).label("call_count"),
                func.sum(ModelCall.input_tokens).label("total_input_tokens"),
                func.sum(ModelCall.output_tokens).label("total_output_tokens"),
                func.sum(ModelCall.cost_usd).label("total_cost")
            ).group_by(ModelCall.agent_type)
            
            if user_id:
                query = query.where(ModelCall.user_id == user_id)
            if start_date:
                query = query.where(ModelCall.created_at >= start_date)
            if end_date:
                query = query.where(ModelCall.created_at <= end_date)
            
            result = await self.db_session.execute(query)
            
            return [
                {
                    "agent_type": row.agent_type,
                    "call_count": row.call_count or 0,
                    "total_input_tokens": row.total_input_tokens or 0,
                    "total_output_tokens": row.total_output_tokens or 0,
                    "total_tokens": (row.total_input_tokens or 0) + (row.total_output_tokens or 0),
                    "total_cost_usd": float(row.total_cost or 0)
                }
                for row in result
            ]
            
        except Exception as e:
            logger.error(f"Failed to get usage by agent: {e}")
            return []
