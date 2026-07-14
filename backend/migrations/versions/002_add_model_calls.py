"""add model_calls table

Revision ID: 002_add_model_calls
Revises: 001_initial_schema
Create Date: 2026-07-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = '002_add_model_calls'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create model_calls table for AI usage tracking."""
    op.create_table(
        'model_calls',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('trace_id', sa.String(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('agent_type', sa.String(), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=False),
        sa.Column('output_tokens', sa.Integer(), nullable=False),
        sa.Column('cost_usd', sa.Float(), nullable=False),
        sa.Column('call_metadata', JSONB, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    
    # Create indexes for common queries
    op.create_index('ix_model_calls_trace_id', 'model_calls', ['trace_id'])
    op.create_index('ix_model_calls_provider', 'model_calls', ['provider'])
    op.create_index('ix_model_calls_model', 'model_calls', ['model'])
    op.create_index('ix_model_calls_agent_type', 'model_calls', ['agent_type'])
    op.create_index('ix_model_calls_user_id', 'model_calls', ['user_id'])
    op.create_index('ix_model_calls_created_at', 'model_calls', ['created_at'])


def downgrade() -> None:
    """Drop model_calls table."""
    op.drop_index('ix_model_calls_created_at')
    op.drop_index('ix_model_calls_user_id')
    op.drop_index('ix_model_calls_agent_type')
    op.drop_index('ix_model_calls_model')
    op.drop_index('ix_model_calls_provider')
    op.drop_index('ix_model_calls_trace_id')
    op.drop_table('model_calls')
