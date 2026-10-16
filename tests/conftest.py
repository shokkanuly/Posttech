import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.services.auth_service import auth_service
from app import seed

# Use in-memory SQLite with StaticPool so all connections share the same memory database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    # Patch seed engine/session to test engine
    old_engine = seed.engine
    old_session = seed.SessionLocal
    seed.engine = engine
    seed.SessionLocal = TestingSessionLocal
    seed.seed_database()
    seed.engine = old_engine
    seed.SessionLocal = old_session
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def employee_token(db_session):
    user = db_session.query(User).filter(User.email == "aruzhan@janapost.kz").first()
    return auth_service.create_access_token(user_id=user.id, role=user.role.value)


@pytest.fixture
def employee_headers(employee_token):
    return {"Authorization": f"Bearer {employee_token}"}


@pytest.fixture
def manager_token(db_session):
    user = db_session.query(User).filter(User.email == "timur@janapost.kz").first()
    return auth_service.create_access_token(user_id=user.id, role=user.role.value)


@pytest.fixture
def manager_headers(manager_token):
    return {"Authorization": f"Bearer {manager_token}"}


@pytest.fixture
def hr_admin_token(db_session):
    user = db_session.query(User).filter(User.email == "aigerim@janapost.kz").first()
    return auth_service.create_access_token(user_id=user.id, role=user.role.value)


@pytest.fixture
def hr_admin_headers(hr_admin_token):
    return {"Authorization": f"Bearer {hr_admin_token}"}
