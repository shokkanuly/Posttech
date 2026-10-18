"""Real migrations, recovery persistence, backup/restore and process isolation."""

import multiprocessing
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.gateway.backup import copy_database
from app.gateway.migrate import VERSION, upgrade_schema
from app.gateway.models import GatewayJob, GatewayNonce, MockDocument
from app.gateway.runtime import GatewayRuntime
from app.integrations.contracts import DocumentRequest
from app.migrate import upgrade_database
from tests.test_gateway_service import config_for, document


def test_gateway_v1_upgrade_backup_restore_and_replay_persistence(tmp_path):
    original = tmp_path / "gateway.db"
    runtime = GatewayRuntime(config_for(original))
    runtime.initialize()
    ack = runtime.submit(DocumentRequest.model_validate(document()))
    runtime.remember_nonce("synthetic-backup-nonce")
    assert runtime.process_one()
    runtime.engine.dispose()
    # Produce the actual previous unversioned schema, while retaining its job/document.
    with sqlite3.connect(original) as db:
        db.execute("ALTER TABLE gateway_jobs DROP COLUMN recovery_key")
        db.execute("DROP TABLE gateway_schema_version")
    upgrade_schema(runtime.engine)
    with runtime.engine.connect() as db:
        assert db.scalar(text("SELECT version FROM gateway_schema_version")) == VERSION
    backup = tmp_path / "backup.db"
    restored = tmp_path / "restored.db"
    copy_database(original, backup)
    copy_database(backup, restored)
    assert restored.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        copy_database(backup, restored)
    recovered = GatewayRuntime(config_for(restored))
    recovered.initialize()
    same = recovered.submit(DocumentRequest.model_validate(document()))
    assert same.gateway_job_id == ack.gateway_job_id and same.status == "REGISTERED"
    with recovered.sessions() as db:
        assert db.query(GatewayJob).count() == db.query(MockDocument).count() == 1
        assert db.query(GatewayNonce).count() == 1
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as rejected:
        recovered.remember_nonce("synthetic-backup-nonce")
    assert rejected.value.status_code == 401
    recovered.engine.dispose()
    runtime.engine.dispose()


def test_gateway_refuses_future_schema(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "future.db"))
    upgrade_schema(engine)
    with engine.begin() as db:
        db.execute(text("UPDATE gateway_schema_version SET version=999"))
    with pytest.raises(RuntimeError, match="newer"):
        upgrade_schema(engine)
    engine.dispose()


def process_gateway(path, start, output):
    runtime = GatewayRuntime(config_for(path))
    start.wait(10)
    try:
        output.put(runtime.process_one())
    finally:
        runtime.engine.dispose()


def test_separate_gateway_processes_claim_one_document(tmp_path):
    path = tmp_path / "two-processes.db"
    runtime = GatewayRuntime(config_for(path))
    runtime.initialize()
    runtime.submit(DocumentRequest.model_validate(document()))
    context = multiprocessing.get_context("spawn")
    start, output = context.Event(), context.Queue()
    workers = [
        context.Process(target=process_gateway, args=(path, start, output)) for _ in range(2)
    ]
    for worker in workers:
        worker.start()
    start.set()
    results = [output.get(timeout=30) for _ in workers]
    for worker in workers:
        worker.join(timeout=30)
        assert worker.exitcode == 0
    assert sorted(results) == [False, True]
    with runtime.sessions() as db:
        assert db.query(GatewayJob).one().status == "REGISTERED"
        assert db.query(MockDocument).count() == 1
    runtime.engine.dispose()


def old_core_database(path):
    engine = create_engine("sqlite:///" + str(path))
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as db:
        config.attributes["connection"] = db
        command.upgrade(config, "0006_gateway_runtime")
        db.exec_driver_sql("PRAGMA foreign_keys=ON")
        db.exec_driver_sql(
            "INSERT INTO users(id,email,password_hash,full_name,role,is_active,created_at) VALUES (1,'synthetic@example.test','unused','Synthetic','EMPLOYEE',1,CURRENT_TIMESTAMP)"
        )
        db.exec_driver_sql(
            "INSERT INTO requests(id,request_code,user_id,type,start_date,status,created_at,updated_at) VALUES (1,'SYNTHETIC',1,'VACATION','2027-01-01','PENDING',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
        db.exec_driver_sql(
            "INSERT INTO request_events(id,request_id,event_type,created_at) VALUES (1,1,'CREATED',CURRENT_TIMESTAMP)"
        )
    return engine


def test_additive_core_upgrade_preserves_request_children(tmp_path):
    engine = old_core_database(tmp_path / "legacy.db")
    upgrade_database(engine)
    with engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM requests")) == 1
        assert db.scalar(text("SELECT count(*) FROM request_events")) == 1
        assert db.scalar(text("SELECT request_code FROM requests")) == "SYNTHETIC"
    engine.dispose()


def test_domain_preflight_refuses_invalid_legacy_without_silent_repair(tmp_path):
    engine = old_core_database(tmp_path / "bad-legacy.db")
    with engine.begin() as db:
        db.execute(text("UPDATE requests SET status='UNKNOWN'"))
    with pytest.raises(RuntimeError, match="operator review"):
        upgrade_database(engine)
    with engine.connect() as db:
        assert db.scalar(text("SELECT status FROM requests")) == "UNKNOWN"
        assert db.scalar(text("SELECT count(*) FROM request_events")) == 1
    engine.dispose()
