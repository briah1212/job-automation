"""add_replay_debug_fields_to_browser_checkpoints

Revision ID: 0b2d243a00d8
Revises: 401ceec878a9
Create Date: 2026-07-21 18:10:08.923199

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0b2d243a00d8'
down_revision: Union[str, None] = '401ceec878a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Autogenerate also picked up a large amount of pre-existing VARCHAR-vs-
    # Enum/index drift unrelated to this change (long-standing, not
    # introduced here) - deliberately excluded rather than bundled in
    # unreviewed. Only the new replay/debug columns below are this
    # migration's actual intent.
    op.add_column('browser_checkpoints', sa.Column('dom_snapshot_object_key', sa.String(), nullable=True))
    op.add_column('browser_checkpoints', sa.Column(
        'decision_reasoning', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'
    ))
    op.add_column('browser_checkpoints', sa.Column(
        'field_sources', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'
    ))
    op.add_column('browser_checkpoints', sa.Column(
        'action_log', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'
    ))


def downgrade() -> None:
    op.drop_column('browser_checkpoints', 'action_log')
    op.drop_column('browser_checkpoints', 'field_sources')
    op.drop_column('browser_checkpoints', 'decision_reasoning')
    op.drop_column('browser_checkpoints', 'dom_snapshot_object_key')
