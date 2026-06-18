"""SQLAlchemy user model. Requires the `db` + `users` extras.

The `user` table is mapped onto the shared declarative ``Base`` from
``app.db.models`` so a single ``Base.metadata`` covers every table in the service.

Migrations
----------
Alembic is not wired into this template yet (only the dependency is declared). Until
it is, create the table directly from the model metadata — e.g. in a one-off script
or an async startup hook:

    import app.users.models  # noqa: F401  (registers the `user` table on Base)
    from app.db.models import Base
    from app.db.session import engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

When you add Alembic, `--autogenerate` will pick this table up from ``Base.metadata``
with no extra wiring.
"""

from __future__ import annotations

from fastapi_users.db import SQLAlchemyBaseUserTableUUID

from app.db.models import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    pass
