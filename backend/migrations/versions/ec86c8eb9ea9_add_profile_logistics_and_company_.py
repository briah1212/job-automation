"""add_profile_logistics_and_company_watches

Revision ID: ec86c8eb9ea9
Revises: 0b2d243a00d8
Create Date: 2026-07-22 06:25:16.564595

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'ec86c8eb9ea9'
down_revision: Union[str, None] = '0b2d243a00d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Personal contact/logistics fields from spec section 6 that weren't
    # captured on Profile yet - non-EEO/demographic (those go through
    # ReusableAnswer instead, matching the spec's "sensitive answers stored
    # separately" principle for protected-class data).
    op.add_column('profiles', sa.Column('date_of_birth', sa.Date(), nullable=True))
    op.add_column('profiles', sa.Column('address_line1', sa.String(), nullable=True))
    op.add_column('profiles', sa.Column('address_line2', sa.String(), nullable=True))
    op.add_column('profiles', sa.Column('city', sa.String(), nullable=True))
    op.add_column('profiles', sa.Column('state', sa.String(), nullable=True))
    op.add_column('profiles', sa.Column('postal_code', sa.String(), nullable=True))
    op.add_column('profiles', sa.Column('country', sa.String(), nullable=True))
    op.add_column('profiles', sa.Column('graduation_year', sa.Integer(), nullable=True))
    op.add_column('profiles', sa.Column('relocation_willingness', sa.String(), nullable=True))
    op.add_column('profiles', sa.Column('salary_expectation_min', sa.Integer(), nullable=True))
    op.add_column('profiles', sa.Column('salary_expectation_max', sa.Integer(), nullable=True))
    op.add_column('profiles', sa.Column('citizenship', sa.String(), nullable=True))
    op.add_column('profiles', sa.Column('clearance_eligible', sa.Boolean(), nullable=True))

    # Company watchlist for Phase 6 (Discovery Automation) - which companies'
    # public ATS job boards to poll, per user, per platform.
    op.create_table(
        'company_watches',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('company_name', sa.String(), nullable=False),
        sa.Column('ats_platform', sa.String(), nullable=False),
        sa.Column('board_identifier', sa.String(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_polled_at', sa.DateTime(), nullable=True),
        sa.Column('last_poll_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('user_id', 'ats_platform', 'board_identifier', name='uq_company_watch_user_platform_board'),
    )


def downgrade() -> None:
    op.drop_table('company_watches')
    op.drop_column('profiles', 'clearance_eligible')
    op.drop_column('profiles', 'citizenship')
    op.drop_column('profiles', 'salary_expectation_max')
    op.drop_column('profiles', 'salary_expectation_min')
    op.drop_column('profiles', 'relocation_willingness')
    op.drop_column('profiles', 'graduation_year')
    op.drop_column('profiles', 'country')
    op.drop_column('profiles', 'postal_code')
    op.drop_column('profiles', 'state')
    op.drop_column('profiles', 'city')
    op.drop_column('profiles', 'address_line2')
    op.drop_column('profiles', 'address_line1')
    op.drop_column('profiles', 'date_of_birth')
