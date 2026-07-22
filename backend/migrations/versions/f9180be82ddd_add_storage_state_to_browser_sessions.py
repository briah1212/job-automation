"""add_storage_state_to_browser_sessions

Revision ID: f9180be82ddd
Revises: ec86c8eb9ea9
Create Date: 2026-07-22 22:09:41.838134

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f9180be82ddd'
down_revision: Union[str, None] = 'ec86c8eb9ea9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Playwright storage_state (cookies + localStorage) for the session's
    # browser context - lets resume() restore real session/cookie state
    # instead of always launching a brand-new, cookie-less browser, which
    # broke any real ATS whose multi-step flow depends on server-side
    # session cookies (confirmed live against Epic's real Avature-hosted
    # careers portal - see docs/browser-state-machine-design.md).
    op.add_column('browser_sessions', sa.Column('storage_state', postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('browser_sessions', 'storage_state')
