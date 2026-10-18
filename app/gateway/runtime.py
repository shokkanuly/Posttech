"""Durable MOCK jobs and callback retries. No payloads or secrets are logged."""

import hashlib
import json
import random
import secrets
import ssl
from datetime import datetime, timedelta, timezone
from typing import cast
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from fastapi import HTTPException
from sqlalchemy import and_, case, create_engine, delete, event, or_, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.gateway.config import GatewaySettings
from app.gateway.connectors import (
    ConnectorRejected,
    MockDocumentolog,
    MockOneC,
    TemporaryConnectorError,
)
from app.gateway.models import GatewayJob, GatewayNonce, GatewayRateLimit, utcnow
from app.integrations import signing
from app.integrations.contracts import (
    BACKOFF_SECONDS,
    DocumentRequest,
    JobStatus,
    RecoveryCommand,
    RegistrationResult,
)


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def status_for(job: GatewayJob) -> JobStatus:
    return JobStatus.model_validate(
        dict(
            gateway_job_id=job.id,
            idempotency_key=job.idempotency_key,
            status=job.status,
            external_ref=job.external_ref,
            mode="MOCK",
            occurred_at=aware(job.updated_at),
            error_code=job.error_code,
            recovery_key=job.recovery_key,
        )
    )


class GatewayRuntime:
    def __init__(self, config: GatewaySettings):
        self.config = config
        args = (
            {"check_same_thread": False, "timeout": 15}
            if config.DATABASE_URL.startswith("sqlite")
            else {}
        )
        self.engine = create_engine(config.DATABASE_URL, connect_args=args, pool_pre_ping=True)
        if self.engine.dialect.name == "sqlite":

            @event.listens_for(self.engine, "connect")
            def pragmas(connection, _record):
                connection.execute("PRAGMA busy_timeout=15000")
                connection.execute("PRAGMA journal_mode=WAL")

        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.one_c = MockOneC(config)
        self.documentolog = MockDocumentolog(config)

    def initialize(self) -> None:
        from app.gateway.migrate import upgrade_schema

        upgrade_schema(self.engine)

    def retry(self, key: str, command: RecoveryCommand) -> JobStatus:
        with self.sessions() as db:
            job = db.query(GatewayJob).filter_by(idempotency_key=key).with_for_update().first()
            if job is None:
                raise HTTPException(404, "Job not found")
            if command.gateway_job_id != job.id:
                raise HTTPException(409, "Recovery job mismatch")
            if job.recovery_key == command.recovery_key or job.status == "REGISTERED":
                return status_for(job)
            if job.status != "DEAD":
                raise HTTPException(409, "Only exhausted transient jobs can be retried")
            claimed = db.execute(
                update(GatewayJob)
                .where(GatewayJob.id == job.id, GatewayJob.status == "DEAD")
                .values(
                    status="PENDING",
                    attempts=0,
                    recovery_key=command.recovery_key,
                    next_attempt_at=utcnow(),
                    updated_at=utcnow(),
                    error_code=None,
                    lease_token=None,
                    lease_until=None,
                    callback_status="WAITING",
                    callback_attempts=0,
                    callback_lease_until=None,
                    callback_lease_token=None,
                ),
                execution_options={"synchronize_session": False},
            )
            if cast(CursorResult, claimed).rowcount != 1:
                raise HTTPException(409, "Recovery state changed")
            db.commit()
            db.refresh(job)
            return status_for(job)

    def remember_nonce(
        self, nonce: str, key_id: str | None = None, *, health_check: bool = False
    ) -> None:
        """Atomically admit a verified caller and consume its nonce before any handler.

        A fixed UTC minute permits at most the configured number per key. Counts are
        durable; denied calls cannot grow the nonce store. Signed GET /health uses
        its own budget. A replay rolls back its quota increment. No signed
        timestamp, payload or client IP owns the window or selects the budget.
        """
        now = utcnow()
        with self.sessions() as db:
            if key_id is not None:
                window = int(now.timestamp()) // 60 * 60
                # Preserve the v3 business hash and its existing counts. Health
                # gets a separate namespace; no table/data migration is needed.
                identity = key_id.encode()
                if health_check:
                    identity = b"\x00health\x00" + identity
                limit = (
                    self.config.HEALTH_REQUESTS_PER_MINUTE
                    if health_check
                    else self.config.REQUESTS_PER_MINUTE
                )
                row = GatewayRateLimit
                insert = sqlite_insert if self.engine.dialect.name == "sqlite" else postgres_insert
                statement = insert(row).values(
                    key_hash=hashlib.sha256(identity).hexdigest(),
                    window_start=window,
                    requests=1,
                )
                accepted = db.execute(
                    statement.on_conflict_do_update(
                        index_elements=[row.key_hash],
                        set_={
                            "window_start": window,
                            "requests": case(
                                (row.window_start == window, row.requests + 1), else_=1
                            ),
                        },
                        where=or_(
                            row.window_start < window,
                            (row.window_start == window) & (row.requests < limit),
                        ),
                    ).returning(row.key_hash)
                ).scalar_one_or_none()
                if accepted is None:
                    raise HTTPException(
                        429,
                        "Integration request limit exceeded",
                        headers={"Retry-After": str(60 - int(now.timestamp()) % 60)},
                    )
            db.execute(
                delete(GatewayNonce).where(GatewayNonce.seen_at < now - timedelta(seconds=900))
            )
            db.add(GatewayNonce(nonce=nonce, seen_at=now))
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                raise HTTPException(401, "Invalid integration signature") from None

    def submit(self, payload: DocumentRequest) -> JobStatus:
        data = payload.model_dump(mode="json", exclude_none=True)
        digest = hashlib.sha256(
            json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        with self.sessions() as db:
            existing = (
                db.query(GatewayJob).filter_by(idempotency_key=payload.idempotency_key).first()
            )
            if existing is None:
                existing = GatewayJob(
                    id="job_" + uuid4().hex,
                    idempotency_key=payload.idempotency_key,
                    payload=data,
                    body_hash=digest,
                    updated_at=utcnow(),
                )
                db.add(existing)
                try:
                    db.commit()
                    db.refresh(existing)
                except IntegrityError:
                    db.rollback()
                    existing = (
                        db.query(GatewayJob)
                        .filter_by(idempotency_key=payload.idempotency_key)
                        .one()
                    )
            if existing.body_hash != digest:
                raise HTTPException(409, "Idempotency key reused with a different request")
            return status_for(existing)

    def process_one(self) -> bool:
        now = utcnow()
        due = or_(
            GatewayJob.status == "PENDING",
            and_(GatewayJob.status == "PROCESSING", GatewayJob.lease_until < now),
        )
        with self.sessions() as db:
            job = (
                db.query(GatewayJob)
                .filter(due, GatewayJob.next_attempt_at <= now)
                .order_by(GatewayJob.created_at)
                .with_for_update(skip_locked=True)
                .first()
            )
            if job is None:
                return False
            token = uuid4().hex
            claimed = db.execute(
                update(GatewayJob)
                .where(GatewayJob.id == job.id, due)
                .values(
                    status="PROCESSING", lease_token=token, lease_until=now + timedelta(seconds=60)
                ),
                execution_options={"synchronize_session": False},
            )
            if cast(CursorResult, claimed).rowcount != 1:
                db.rollback()
                return False
            job_id = job.id
            db.commit()
        with self.sessions() as db:
            job = (
                db.query(GatewayJob).filter_by(id=job_id, lease_token=token).with_for_update().one()
            )
            job.attempts += 1
            try:
                job.external_ref = self.documentolog.register(db, job)
                job.status = "REGISTERED"
                job.error_code = None
            except TemporaryConnectorError:
                job.error_code = "DOCUMENTOLOG_UNAVAILABLE"
                if job.attempts <= len(BACKOFF_SECONDS):
                    job.status = "PENDING"
                    job.next_attempt_at = now + timedelta(
                        seconds=BACKOFF_SECONDS[job.attempts - 1] * random.uniform(0.8, 1.2)
                    )
                else:
                    job.status = "DEAD"
            except ConnectorRejected:
                job.status, job.error_code = "FAILED", "DOCUMENTOLOG_REJECTED"
            job.updated_at = utcnow()
            job.lease_token = None
            job.lease_until = None
            if job.status in {"REGISTERED", "FAILED", "DEAD"}:
                job.callback_status = "PENDING"
                job.callback_next_at = utcnow()
            db.commit()
        return True

    def send_callback(self, result: RegistrationResult) -> int:
        if not self.config.CALLBACK_KEY:
            return 0
        body = result.model_dump_json().encode()
        url = urlsplit(self.config.CALLBACK_URL)
        path = url.path + ("?" + url.query if url.query else "")
        headers = signing.sign(
            self.config.CALLBACK_KEY_ID,
            self.config.CALLBACK_KEY,
            "POST",
            path,
            body,
            nonce=result.nonce,
        )
        headers["Content-Type"] = "application/json"
        tls = ssl.create_default_context(cafile=self.config.TLS_CA or None)
        tls.minimum_version = ssl.TLSVersion.TLSv1_3
        if self.config.TLS_CERT:
            tls.load_cert_chain(self.config.TLS_CERT, self.config.TLS_KEY or None)
        try:
            response = httpx.post(
                self.config.CALLBACK_URL, content=body, headers=headers, timeout=5, verify=tls
            )
            if 200 <= response.status_code < 300:
                try:
                    acknowledgement = response.json()
                except ValueError:
                    return 502
                if not isinstance(acknowledgement, dict) or not isinstance(
                    acknowledgement.get("applied"), bool
                ):
                    return 502
            return response.status_code
        except httpx.HTTPError:
            return 0

    def callback_one(self) -> bool:
        now = utcnow()
        due = and_(
            GatewayJob.callback_status == "PENDING",
            GatewayJob.callback_next_at <= now,
            or_(GatewayJob.callback_lease_until.is_(None), GatewayJob.callback_lease_until < now),
        )
        with self.sessions() as db:
            job = db.query(GatewayJob).filter(due).with_for_update(skip_locked=True).first()
            if job is None:
                return False
            token = uuid4().hex
            claimed = db.execute(
                update(GatewayJob)
                .where(GatewayJob.id == job.id, due)
                .values(
                    callback_lease_token=token, callback_lease_until=now + timedelta(seconds=60)
                ),
                execution_options={"synchronize_session": False},
            )
            if cast(CursorResult, claimed).rowcount != 1:
                db.rollback()
                return False
            job_id = job.id
            db.commit()
            result = RegistrationResult(**status_for(job).model_dump(), nonce=secrets.token_hex(16))
        code = self.send_callback(result)
        with self.sessions() as db:
            job = (
                db.query(GatewayJob)
                .filter_by(id=job_id, callback_lease_token=token)
                .with_for_update()
                .first()
            )
            if job is None:
                return True  # An authorized new generation superseded this in-flight callback.
            job.callback_attempts += 1
            job.callback_lease_token = None
            job.callback_lease_until = None
            if 200 <= code < 300:
                job.callback_status = "DELIVERED"
            elif job.callback_attempts <= len(BACKOFF_SECONDS):
                job.callback_next_at = now + timedelta(
                    seconds=BACKOFF_SECONDS[job.callback_attempts - 1] * random.uniform(0.8, 1.2)
                )
            else:
                # The terminal result remains readable through GET for reconciliation.
                job.callback_status = "DEAD"
            db.commit()
        return True

    def tick(self) -> None:
        self.process_one()
        self.callback_one()
