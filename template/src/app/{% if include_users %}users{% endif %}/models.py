"""SQLAlchemy user model. Requires the `db` + `users` extras.

The `user` table is mapped onto the shared declarative ``Base`` from
``app.db.models`` so a single ``Base.metadata`` covers every table in the service.

Migrations
----------
Alembic is wired in. An initial migration covering this table (and the example
``items`` table) ships in ``migrations/versions/`` — apply it with ``just migrate``
(``alembic upgrade head``). After changing this model, generate a new migration with
``just migration "describe the change"`` (``alembic revision --autogenerate``);
``migrations/env.py`` imports this module, so autogenerate always sees the ``user`` table.
"""

from __future__ import annotations

from fastapi_users.db import SQLAlchemyBaseUserTableUUID

from app.db.models import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    pass
