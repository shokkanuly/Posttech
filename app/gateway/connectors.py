"""Local MOCK connectors. No vendor URLs, accounts, payments or signature service."""

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.gateway.config import GatewaySettings
from app.gateway.models import GatewayJob, MockDocument
from app.integrations.contracts import EmployeeSnapshot


class TemporaryConnectorError(Exception):
    pass


class ConnectorRejected(Exception):
    pass


class MockDocumentolog:
    def __init__(self, config: GatewaySettings):
        self.config = config

    def register(self, db: Session, job: GatewayJob) -> str:
        existing = db.get(MockDocument, job.idempotency_key)
        if existing:
            return existing.external_ref
        if self.config.MOCK_DOCUMENTOLOG_FAILURE == "temporary":
            raise TemporaryConnectorError
        if self.config.MOCK_DOCUMENTOLOG_FAILURE == "validation":
            raise ConnectorRejected
        reference = "MOCK-DOC-" + job.id.removeprefix("job_")
        db.add(MockDocument(idempotency_key=job.idempotency_key, external_ref=reference))
        db.flush()
        return reference


class MockOneC:
    def __init__(self, config: GatewaySettings):
        self.config = config
        if config.MOCK_EMPLOYEES_FILE:
            rows = json.loads(Path(config.MOCK_EMPLOYEES_FILE).read_text())
        else:
            rows = json.loads(Path(__file__).with_name("mock_employees.json").read_text())
        self.rows = [EmployeeSnapshot.model_validate(row) for row in rows]
        if len(self.rows) > 1000 or len({r.employee_code for r in self.rows}) != len(self.rows):
            raise ValueError("MOCK fixture must contain at most 1000 unique employee codes")

    def employees(self, updated_since: datetime | None = None) -> list[EmployeeSnapshot]:
        if self.config.MOCK_ONE_C_UNAVAILABLE:
            raise TemporaryConnectorError
        return [r for r in self.rows if updated_since is None or r.as_of > updated_since]

    def cursor(self, previous: datetime | None) -> datetime:
        return max(
            [r.as_of for r in self.rows] + [previous or datetime(1970, 1, 1, tzinfo=timezone.utc)]
        )
