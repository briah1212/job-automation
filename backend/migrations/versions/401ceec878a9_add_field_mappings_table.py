"""add_field_mappings_table

Revision ID: 401ceec878a9
Revises: b3f1c9a2d4e7
Create Date: 2026-07-21 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '401ceec878a9'
down_revision: Union[str, None] = 'b3f1c9a2d4e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'field_mappings',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('ats_platform', sa.String(), nullable=False, index=True),
        sa.Column('domain', sa.String(), nullable=False, index=True),
        sa.Column('form_fingerprint', sa.String(), nullable=False, index=True),
        sa.Column('field_name', sa.String(), nullable=False),
        sa.Column('label', sa.Text(), nullable=True),
        sa.Column('canonical_name', sa.String(), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('reviewed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('use_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('ats_platform', 'domain', 'form_fingerprint', 'field_name', name='uq_field_mappings_form_field'),
    )


def downgrade() -> None:
    op.drop_table('field_mappings')
