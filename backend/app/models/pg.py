import uuid

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPrimaryKey
from app.models.owner import Owner


class Pg(UUIDPrimaryKey, Timestamps, Base):
    """A paying-guest property, created automatically at signup.

    The UI exposes one PG per owner; the schema allows several so multiple PGs
    can be supported later without a rewrite (CLAUDE.md §3).
    """

    __tablename__ = "pgs"
    __table_args__ = (
        CheckConstraint("default_rent_due_day BETWEEN 1 AND 28", name="default_rent_due_day_range"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("owners.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), default="My PG")
    address: Mapped[str | None] = mapped_column(Text)
    default_rent_due_day: Mapped[int] = mapped_column(SmallInteger, default=5, server_default="5")

    owner: Mapped[Owner] = relationship(back_populates="pgs")
