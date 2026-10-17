import json
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

with tempfile.TemporaryDirectory(prefix="janamen-qa-probe-") as temp:
    os.environ.update(
        ENVIRONMENT="test",
        DEMO_MODE="true",
        DEMO_PASSWORD="Password123!",
        SECRET_KEY="qa-disposable-" + "x" * 40,
        DATABASE_URL="sqlite:///" + temp + "/qa.db",
        AI_PROVIDER="grounded_knowledge",
        GEMINI_API_KEY="",
        GEMINI_DATA_SHARING_APPROVED="false",
        INTEGRATION_GATEWAY_URL="",
        INTEGRATION_INBOUND_KEYS="{}",
    )
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, event
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import sessionmaker

    import app.main as main
    from app.database import get_db
    from app.migrate import upgrade_database
    from app.seed import seed_database

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    upgrade_database(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        seed_database(session)
    report = {"environment": "fresh disposable SQLite; synthetic seed only", "database_probes": {}}
    probes = {
        "negative_balance": "UPDATE employee_profiles SET leave_balance_days=-1 WHERE user_id=3",
        "reversed_request_dates": "UPDATE requests SET start_date='2026-12-31',end_date='2026-01-01' WHERE id=1",
        "unknown_request_status": "UPDATE requests SET status='UNKNOWN_QA' WHERE id=1",
        "foreign_key": "UPDATE notifications SET user_id=999999 WHERE id=1",
        "unique_employee_code": "UPDATE employee_profiles SET employee_code=(SELECT employee_code FROM employee_profiles WHERE user_id=2) WHERE user_id=3",
    }
    for name, sql in probes.items():
        with engine.connect() as connection:
            try:
                result = connection.exec_driver_sql(sql)
                assert result.rowcount == 1
                report["database_probes"][name] = {"write_rejected": False}
            except IntegrityError:
                report["database_probes"][name] = {"write_rejected": True}
            finally:
                connection.rollback()

    def override_db():
        with factory() as session:
            try:
                yield session
            except Exception:
                session.rollback()
                raise

    main.app.dependency_overrides[get_db] = override_db
    main.engine = engine
    main.seed_database = lambda: None
    with TestClient(main.app, raise_server_exceptions=False) as client:
        logged = client.post(
            "/api/v1/auth/login",
            json={"email": "aruzhan@janapost.kz", "password": os.environ["DEMO_PASSWORD"]},
        )
        assert logged.status_code == 200
        headers = {"Authorization": "Bearer " + logged.json()["access_token"]}
        payload = {
            "type": "Advance payment",
            "start_date": (date.today() + timedelta(days=10)).isoformat(),
            "amount": 100,
            "reason": "synthetic QA duplicate probe",
        }
        rows = [client.post("/api/v1/requests", headers=headers, json=payload) for _ in range(2)]
        report["identical_advance_submission"] = {
            "http_statuses": [r.status_code for r in rows],
            "distinct_records": len({r.json().get("id") for r in rows}),
        }
        assert all(r.status_code == 201 for r in rows)
    engine.dispose()
    Path("docs/evidence/qa-2026-10-17/extra-probes.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report))
