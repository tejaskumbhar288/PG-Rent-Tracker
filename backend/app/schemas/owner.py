import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OwnerRead(BaseModel):
    """Public view of an owner.

    Fields are listed explicitly rather than dumped from the model, so
    ``password_hash`` can never reach a response.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    phone: str
    email: str | None
    created_at: datetime
