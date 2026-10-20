"""SQLAlchemy models.

Importing this package registers every model on ``Base.metadata``, which is what
Alembic's ``--autogenerate`` and the test harness's ``create_all`` diff against.
"""

from app.models.owner import Owner
from app.models.pg import Pg

__all__ = ["Owner", "Pg"]
