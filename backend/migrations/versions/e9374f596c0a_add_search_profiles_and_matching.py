"""add_search_profiles_and_matching

Revision ID: e9374f596c0a
Revises: 002_add_model_calls
Create Date: 2026-07-14 16:45:46.285571

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e9374f596c0a'
down_revision: Union[str, None] = '002_add_model_calls'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create search_profiles table
    op.create_table(
        'search_profiles',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=True, server_default='true', index=True),
        sa.Column('career_categories', sa.dialects.postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('include_titles', sa.dialects.postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('exclude_titles', sa.dialects.postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('include_skills', sa.dialects.postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('exclude_skills', sa.dialects.postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('locations', sa.dialects.postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('remote_policy', sa.String(), nullable=True),
        sa.Column('min_salary', sa.Integer(), nullable=True),
        sa.Column('employment_types', sa.dialects.postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('seniority_levels', sa.dialects.postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('companies', sa.dialects.postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('excluded_companies', sa.dialects.postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Create job_match_scores table
    op.create_table(
        'job_match_scores',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('canonical_jobs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('overall_score', sa.Integer(), nullable=False, index=True),
        sa.Column('skill_score', sa.Float(), nullable=False),
        sa.Column('experience_score', sa.Float(), nullable=False),
        sa.Column('seniority_score', sa.Float(), nullable=False),
        sa.Column('location_score', sa.Float(), nullable=False),
        sa.Column('salary_score', sa.Float(), nullable=False),
        sa.Column('hard_blockers', sa.dialects.postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('strong_matches', sa.dialects.postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('soft_gaps', sa.dialects.postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('missing_info', sa.dialects.postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('recommended_action', sa.String(), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('matched_resume_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('resume_versions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('resume_selection_rationale', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('job_match_scores')
    op.drop_table('search_profiles')
