"""owners and pgs

Revision ID: 0002_owners_and_pgs
Revises: 0001_baseline
Create Date: 2026-10-20

F1: the owner account, plus the PG that is created for them at signup. Both
tables arrive together because signup inserts an owner and their PG in one
transaction (FEATURES.md F1). Constraint names come from the naming convention
on ``Base.metadata``, so they are spelled out here with ``op.f()``.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_owners_and_pgs"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "owners",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=16), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_owners")),
        sa.UniqueConstraint("email", name=op.f("uq_owners_email")),
        sa.UniqueConstraint("phone", name=op.f("uq_owners_phone")),
    )
    op.create_table(
        "pgs",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("default_rent_due_day", sa.SmallInteger(), server_default="5", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "default_rent_due_day BETWEEN 1 AND 28",
            name=op.f("ck_pgs_default_rent_due_day_range"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_pgs_owner_id_owners"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pgs")),
    )
    op.create_index(op.f("ix_pgs_owner_id"), "pgs", ["owner_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_pgs_owner_id"), table_name="pgs")
    op.drop_table("pgs")
    op.drop_table("owners")
