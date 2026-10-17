"""Every test owns its database, startup engine and real revocable sessions."""

import os
import tempfile
from datetime import date
from pathlib import Path
from uuid import uuid4

os.environ.update(
    ENVIRONMENT="test",
    DEMO_MODE="true",
    DEMO_PASSWORD="Password123!",
    SECRET_KEY="test-only-key-not-for-deployment-" + "x" * 32,
    DATABASE_URL="sqlite:///"
    + str(Path(tempfile.gettempdir()) / "janamen-unused-test-bootstrap.db"),
    ENABLE_MOCK_INTEGRATIONS="false",
    AI_CONFIDENCE_THRESHOLD="0.8",
    AI_PROVIDER="grounded_knowledge",
    AI_RETRIEVAL_MODE="lexical",
    GEMINI_API_KEY="",
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import app.main as main_module
from app.database import get_db
from app.main import app
from app.migrate import upgrade_database
from app.seed import seed_database
from app.services import request_service as request_service_module
from app.services.auth_service import login_limiter


@pytest.fixture(autouse=True)
def fixed_business_date(monkeypatch):
    """Request rules reject past dates; pin "today" so dated scenarios never expire."""
    monkeypatch.setattr(request_service_module, "request_today", lambda: date(2026, 10, 15))


@pytest.fixture
def db_engine(tmp_path):
    # TEST_DATABASE_URL=postgresql+psycopg://... runs the whole suite on PostgreSQL;
    # Each test owns a unique schema; existing schemas are never dropped.
    postgres_url = os.environ.get("TEST_DATABASE_URL", "")
    if postgres_url.startswith("postgresql"):
        schema = "janamen_test_" + uuid4().hex
        admin_engine = create_engine(postgres_url)
        with admin_engine.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        engine = create_engine(postgres_url, connect_args={"options": f"-csearch_path={schema}"})
    else:
        engine = create_engine(
            "sqlite:///" + str(tmp_path / "test.db"),
            connect_args={"check_same_thread": False, "timeout": 15},
        )

        @event.listens_for(engine, "connect")
        def pragmas(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=15000")

    try:
        upgrade_database(engine)
        with sessionmaker(bind=engine)() as session:
            seed_database(session)
        yield engine
    finally:
        engine.dispose()
        if postgres_url.startswith("postgresql"):
            with admin_engine.begin() as connection:
                connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
            admin_engine.dispose()


@pytest.fixture
def db_session(db_engine):
    with sessionmaker(bind=db_engine)() as session:
        yield session


@pytest.fixture
def client(db_engine, monkeypatch):
    factory = sessionmaker(bind=db_engine)

    def override_db():
        with factory() as session:
            try:
                yield session
            except Exception:
                session.rollback()
                raise

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(main_module, "engine", db_engine)
    # The fixture already seeded its own database. Never run startup against user storage.
    monkeypatch.setattr(main_module, "seed_database", lambda: None)
    login_limiter.failures.clear()
    with TestClient(app, raise_server_exceptions=False) as result:
        yield result
    app.dependency_overrides.clear()


def login(client, email):
    result = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    assert result.status_code == 200, result.text
    return result.json()["access_token"]


@pytest.fixture
def employee_token(client):
    return login(client, "aruzhan@janapost.kz")


@pytest.fixture
def employee_headers(employee_token):
    return {"Authorization": "Bearer " + employee_token}


@pytest.fixture
def manager_token(client):
    return login(client, "timur@janapost.kz")


@pytest.fixture
def manager_headers(manager_token):
    return {"Authorization": "Bearer " + manager_token}


@pytest.fixture
def hr_admin_token(client):
    return login(client, "aigerim@janapost.kz")


@pytest.fixture
def hr_admin_headers(hr_admin_token):
    return {"Authorization": "Bearer " + hr_admin_token}
