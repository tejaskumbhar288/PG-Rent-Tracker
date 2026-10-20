"""baseline

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-20

Empty baseline so ``alembic upgrade head`` runs on an empty DB and is
idempotent. Domain tables arrive with their own feature migrations.
"""

from collections.abc import Sequence

import sqlalchemy as sa  # noqa: F401

from alembic import op  # noqa: F401

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
