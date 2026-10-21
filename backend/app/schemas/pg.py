import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PgRead(BaseModel):
    """Public view of a PG.

    Fields are listed explicitly rather than dumped from the model, so
    ``owner_id`` can never reach a response.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    address: str | None
    default_rent_due_day: int
    created_at: datetime


# For an optional field, ``None`` is how Pydantic hears "not supplied", so an
# explicit ``null`` for either of these has to be rejected rather than quietly
# ignored: both columns are NOT NULL, and letting it through would turn a bad
# request into a 500 at commit time instead of a 422 at the edge.
_NOT_NULLABLE = ("name", "default_rent_due_day")


class PgUpdate(BaseModel):
    """Partial update of the owner's PG — every field is optional.

    Only the fields a request mentions are changed, so the route dumps this with
    ``exclude_unset=True``.
    """

    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    address: Annotated[str, Field(max_length=500)] | None = None
    default_rent_due_day: Annotated[int, Field(ge=1, le=28)] | None = None

    @model_validator(mode="before")
    @classmethod
    def _reject_explicit_nulls(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for field in _NOT_NULLABLE:
                if field in data and data[field] is None:
                    raise ValueError(f"{field} cannot be null")
        return data

    @field_validator("name", mode="before")
    @classmethod
    def _trim(cls, value: object) -> object:
        # Before, not after: " " would otherwise satisfy min_length as 3 chars
        # and be stored as a blank name.
        return value.strip() if isinstance(value, str) else value

    @field_validator("address", mode="before")
    @classmethod
    def _blank_is_absent(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("default_rent_due_day", mode="before")
    @classmethod
    def _reject_bool(cls, value: object) -> object:
        # ``isinstance(True, int)`` is True, which is why Pydantic's lax mode
        # happily reads ``true`` as day 1. A boolean is not a day of the month.
        if isinstance(value, bool):
            raise ValueError("must be a whole number")
        return value
