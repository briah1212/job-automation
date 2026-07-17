"""add_phase3_tailoring_review_tables

Revision ID: 31238ad4becf
Revises: e9374f596c0a
Create Date: 2026-07-17 20:39:17.958500

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '31238ad4becf'
down_revision: Union[str, None] = 'e9374f596c0a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create profile_facts table
    op.create_table(
        'profile_facts',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('fact_type', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('source_type', sa.String(), nullable=False),
        sa.Column('source_identifier', sa.String(), nullable=True),
        sa.Column('original_text', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('user_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('permitted_uses', sa.dialects.postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create reusable_answers table
    op.create_table(
        'reusable_answers',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('canonical_question', sa.Text(), nullable=False),
        sa.Column('semantic_variants', sa.dialects.postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('exact_answer', sa.Text(), nullable=False),
        sa.Column('allowed_paraphrasing', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('risk_level', sa.String(), nullable=False),
        sa.Column('categories', sa.dialects.postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('expiration_date', sa.DateTime(), nullable=True),
        sa.Column('user_approved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create resume_claims table
    op.create_table(
        'resume_claims',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('resume_version_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('resume_versions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('section', sa.String(), nullable=False),
        sa.Column('claim_text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
    )

    # Create resume_claim_sources table
    op.create_table(
        'resume_claim_sources',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('resume_claim_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('resume_claims.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('profile_fact_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('profile_facts.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('strength', sa.Float(), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=True),
    )

    # Create document_renderings table
    op.create_table(
        'document_renderings',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('resume_version_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('resume_versions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('format', sa.String(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
    )

    # Create document_locks table
    op.create_table(
        'document_locks',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('resume_family_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('resume_families.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('lock_type', sa.String(), nullable=False),
        sa.Column('target_ref', sa.String(), nullable=False),
        sa.Column('value', sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
    )

    # Create application_questions table
    op.create_table(
        'application_questions',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('application_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('question_type', sa.String(), nullable=False),
        sa.Column('risk_level', sa.String(), nullable=False),
        sa.Column('canonical_reusable_answer_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('reusable_answers.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
    )

    # Create application_answers table
    op.create_table(
        'application_answers',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('application_question_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('application_questions.id', ondelete='CASCADE'), nullable=False, unique=True, index=True),
        sa.Column('answer_text', sa.Text(), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('approved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create application_answer_sources table
    op.create_table(
        'application_answer_sources',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('application_answer_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('application_answers.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('profile_fact_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('profile_facts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('explanation', sa.Text(), nullable=True),
    )

    # Create application_reviews table
    op.create_table(
        'application_reviews',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('application_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('passed', sa.Boolean(), nullable=False),
        sa.Column('blocking_findings', sa.dialects.postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('warnings', sa.dialects.postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('recommended_correction', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table('application_reviews')
    op.drop_table('application_answer_sources')
    op.drop_table('application_answers')
    op.drop_table('application_questions')
    op.drop_table('document_locks')
    op.drop_table('document_renderings')
    op.drop_table('resume_claim_sources')
    op.drop_table('resume_claims')
    op.drop_table('reusable_answers')
    op.drop_table('profile_facts')
