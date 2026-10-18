"""Versioned, additive upgrades of the gateway's independent job store."""

from sqlalchemy import Column, Integer, MetaData, Table, inspect, select, text

from app.gateway.models import GatewayBase

VERSION = 3
metadata = MetaData()
version = Table(
    "gateway_schema_version",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("version", Integer, nullable=False),
)


def upgrade_schema(engine):
    with engine.begin() as connection:
        metadata.create_all(connection)
        current = connection.execute(select(version.c.version).where(version.c.id == 1)).scalar()
        if current is not None and current > VERSION:
            raise RuntimeError("Gateway schema is newer than this service")
        tables = inspect(connection).get_table_names()
        if "gateway_jobs" in tables:
            columns = {c["name"] for c in inspect(connection).get_columns("gateway_jobs")}
            if not {"id", "idempotency_key", "payload", "callback_status"} <= columns:
                raise RuntimeError("Unrecognized gateway schema; operator review required")
            if "recovery_key" not in columns:
                connection.execute(
                    text("ALTER TABLE gateway_jobs ADD COLUMN recovery_key VARCHAR(32)")
                )
        GatewayBase.metadata.create_all(connection)
        if current is None:
            connection.execute(version.insert().values(id=1, version=VERSION))
        elif current < VERSION:
            connection.execute(version.update().where(version.c.id == 1).values(version=VERSION))
