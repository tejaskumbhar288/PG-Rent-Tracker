"""Reading and editing the owner's PG.

The PG row itself is created at signup (``services/auth.py``); F2 only reads and
updates it. Routes stay thin (CLAUDE.md §9), so "which PG is the current one?"
and the partial-update rule both live here.
"""

import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.pg import Pg

DEFAULT_PG_NAME = "My PG"
DEFAULT_RENT_DUE_DAY = 5


def get_pg_for_owner(db: Session, owner_id: uuid.UUID) -> Pg | None:
    """The owner's current PG, or ``None`` when they have no PG row.

    One PG per owner is a UI rule, not a schema one (CLAUDE.md §3), so this
    picks the oldest row deterministically. The ``id`` tie-break matters: rows
    written in the same transaction share ``created_at``, and without it the
    "current" PG could differ from one request to the next.
    """
    return db.scalar(
        select(Pg).where(Pg.owner_id == owner_id).order_by(Pg.created_at, Pg.id).limit(1)
    )


def update_pg(db: Session, pg: Pg, changes: Mapping[str, Any]) -> Pg:
    """Apply a partial update and return the refreshed PG.

    ``changes`` comes from ``PgUpdate.model_dump(exclude_unset=True)``, so a key
    is present only if the request actually mentioned it — which is what keeps
    ``address: null`` ("clear it") distinguishable from an absent address
    ("leave it alone"). An empty mapping touches nothing at all, so a no-op
    PATCH leaves ``updated_at`` where it was.
    """
    if not changes:
        return pg

    for field, value in changes.items():
        setattr(pg, field, value)
    db.commit()
    db.refresh(pg)
    return pg
