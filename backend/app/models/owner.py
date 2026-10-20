from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.pg import Pg


class Owner(UUIDPrimaryKey, Timestamps, Base):
    """A PG owner — the only kind of app user (CLAUDE.md §2).

    ``phone`` is the primary login identifier and is always stored in E.164
    (``+91XXXXXXXXXX``); ``email`` is optional but unique when present.
    """

    __tablename__ = "owners"

    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(16), unique=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    pgs: Mapped[list["Pg"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
