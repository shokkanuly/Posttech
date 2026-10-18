"""Independent application workers against an explicitly disposable PostgreSQL schema."""

import multiprocessing
import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.gateway.models import GatewayJob, MockDocument
from app.gateway.runtime import GatewayRuntime, status_for
from app.integrations import outbox
from app.integrations.contracts import DocumentRequest
from app.models.integration import IntegrationOutbox
from app.models.notification import Notification
from app.models.request import Request
from tests.test_gateway_service import config_for
from tests.test_integration_gateway import approve_vacation


def dispatch_process(url, schema, store, entered, release, output, crash_after_accept=False):
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    runtime = GatewayRuntime(config_for(store))
    settings.INTEGRATION_GATEWAY_URL = "http://synthetic.invalid"

    def send(_path, body, _key):
        result = runtime.submit(DocumentRequest.model_validate_json(body))
        entered.set()
        if crash_after_accept:
            # Gateway acceptance committed; application ack/attempt transaction is lost.
            os._exit(23)
        assert release.wait(20), "Parent did not release the simulated network response"
        return 202, result.model_dump(mode="json")

    try:
        with sessionmaker(bind=engine)() as db:
            output.put(outbox.dispatch_one(db, send=send))
    finally:
        engine.dispose()
        runtime.engine.dispose()


@pytest.mark.parametrize("crash_after_accept", [False, True])
def test_postgresql_independent_workers_and_acceptance_crash(
    client,
    db_engine,
    db_session,
    employee_headers,
    manager_headers,
    monkeypatch,
    tmp_path,
    crash_after_accept,
):
    if db_engine.dialect.name != "postgresql":
        pytest.skip("Requires TEST_DATABASE_URL; SQLite cannot prove PostgreSQL SKIP LOCKED")
    monkeypatch.setattr(settings, "INTEGRATION_GATEWAY_URL", "http://synthetic.invalid")
    rid = approve_vacation(client, employee_headers, manager_headers)
    with db_engine.connect() as connection:
        schema = connection.scalar(text("SELECT current_schema()"))
    url = db_engine.url.render_as_string(hide_password=False)
    store = tmp_path / "gateway.db"
    runtime = GatewayRuntime(config_for(store))
    runtime.initialize()
    context = multiprocessing.get_context("spawn")
    entered, release, output = context.Event(), context.Event(), context.Queue()
    workers = []
    try:
        first = context.Process(
            target=dispatch_process,
            args=(url, schema, store, entered, release, output, crash_after_accept),
        )
        workers.append(first)
        first.start()
        assert entered.wait(20)
        if crash_after_accept:
            first.join(20)
            assert first.exitcode == 23
            db_session.expire_all()
            task = db_session.query(IntegrationOutbox).one()
            assert task.status == "PENDING" and task.gateway_job_id is None
            db_session.rollback()
        else:
            # First process holds the row lock while the gateway ack is in flight.
            # The second must skip it and return before the first can commit.
            second = context.Process(
                target=dispatch_process,
                args=(url, schema, store, entered, release, output),
            )
            workers.append(second)
            second.start()
            assert output.get(timeout=20) is False
            second.join(20)
            assert second.exitcode == 0
        release.set()
        if crash_after_accept:
            retry = context.Process(
                target=dispatch_process,
                args=(url, schema, store, entered, release, output),
            )
            workers.append(retry)
            retry.start()
        assert output.get(timeout=20) is True
        for worker in workers:
            worker.join(20)
            assert worker.exitcode == (23 if worker is first and crash_after_accept else 0)
        db_session.expire_all()
        task = db_session.query(IntegrationOutbox).one()
        original_key, original_body = task.idempotency_key, task.payload.copy()
        with runtime.sessions() as db:
            job = db.query(GatewayJob).one()
            assert job.id == task.gateway_job_id and job.idempotency_key == original_key
        assert runtime.process_one()
        with runtime.sessions() as db:
            result = status_for(db.query(GatewayJob).one()).model_dump(mode="json")
            assert db.query(MockDocument).count() == 1
        task.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db_session.commit()
        assert outbox.dispatch_one(db_session, get=lambda _: (200, result))
        assert db_session.get(Request, rid).integration_status == "REGISTERED"
        assert task.idempotency_key == original_key and task.payload == original_body
        assert (
            db_session.query(Notification).filter_by(title="MOCK document registered").count() == 1
        )
        assert not outbox.dispatch_one(db_session)
    finally:
        release.set()
        for worker in workers:
            worker.join(5)
            if worker.is_alive():
                worker.terminate()
                worker.join(5)
        runtime.engine.dispose()
