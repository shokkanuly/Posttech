from alembic import context

from app import models  # noqa: F401
from app.database import Base, engine


def run(connection):
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


provided = context.config.attributes.get("connection")
if provided is not None:
    run(provided)
else:
    with engine.begin() as connection:
        run(connection)
