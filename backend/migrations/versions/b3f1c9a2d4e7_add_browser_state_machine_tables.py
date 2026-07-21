"""add_browser_state_machine_tables

Revision ID: b3f1c9a2d4e7
Revises: 5099567ff0fb
Create Date: 2026-07-20 16:30:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b3f1c9a2d4e7'
down_revision: Union[str, None] = '5099567ff0fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'browser_sessions',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('application_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('workflow_task_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('workflow_tasks.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('session_key', sa.String(), nullable=False, unique=True, index=True),
        sa.Column('browser_state', sa.String(), nullable=False),
        sa.Column('ats_platform', sa.String(), nullable=True),
        sa.Column('tenant_key', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, index=True),
        sa.Column('pause_reason', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        'browser_checkpoints',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('session_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('browser_sessions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('browser_state', sa.String(), nullable=False),
        sa.Column('step', sa.String(), nullable=False),
        sa.Column('url', sa.String(), nullable=False),
        sa.Column('screenshot_object_key', sa.String(), nullable=True),
        sa.Column('filled_fields', sa.dialects.postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('form_state', sa.dialects.postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('page_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
    )

    op.create_table(
        'ats_credentials',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('ats_platform', sa.String(), nullable=False),
        sa.Column('tenant_key', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('encrypted_password', sa.LargeBinary(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('user_id', 'ats_platform', 'tenant_key', name='uq_ats_credentials_user_platform_tenant'),
    )


def downgrade() -> None:
    op.drop_table('ats_credentials')
    op.drop_table('browser_checkpoints')
    op.drop_table('browser_sessions')
