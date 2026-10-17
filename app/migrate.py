"""Explicit schema upgrades; startup never drops, resets or silently migrates data."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy.engine import Engine

HEAD = "0006_profile_updates"


class SchemaNotCurrentError(RuntimeError):
    pass


def upgrade_database(target: Engine) -> None:
    root = Path(__file__).resolve().parent.parent
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    with target.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def require_current_schema(target: Engine) -> None:
    with target.connect() as connection:
        if MigrationContext.configure(connection).get_current_revision() != HEAD:
            raise SchemaNotCurrentError(
                "Database schema is not current. Run: python -m app.migrate"
            )


if __name__ == "__main__":
    from app.database import engine

    upgrade_database(engine)
    print(f"Database schema upgraded to {HEAD}; existing rows preserved.")
