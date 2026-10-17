from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.migrate import HEAD, require_current_schema, upgrade_database


def baseline(engine):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0001_baseline")


def test_empty_database_upgrade_is_repeatable(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "fresh.db"))
    upgrade_database(engine)
    upgrade_database(engine)
    require_current_schema(engine)
    assert "auth_sessions" in inspect(engine).get_table_names()
    assert {"is_approved", "approved_at"}.issubset(
        {c["name"] for c in inspect(engine).get_columns("knowledge_documents")}
    )
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == HEAD
    engine.dispose()


def test_legacy_rows_are_preserved_and_sources_require_approval(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "legacy.db"))
    baseline(engine)
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO users(id,email,password_hash,full_name,role,is_active,created_at) VALUES (1,'legacy@example.test','legacy-hash','Synthetic Legacy','EMPLOYEE',1,CURRENT_TIMESTAMP)"
            )
        )
        c.execute(
            text(
                "INSERT INTO knowledge_documents(id,title,category,version,is_active,created_at,updated_at) VALUES (1,'Legacy source','HR','1',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        )
        # This disposable fixture models the original database, which had no version table.
        c.exec_driver_sql("DROP TABLE alembic_version")
    upgrade_database(engine)
    with engine.connect() as c:
        assert (
            c.execute(text("SELECT password_hash FROM users WHERE id=1")).scalar() == "legacy-hash"
        )
        assert (
            c.execute(text("SELECT is_approved FROM knowledge_documents WHERE id=1")).scalar() == 0
        )
        assert c.execute(text("SELECT COUNT(*) FROM users")).scalar() == 1
    engine.dispose()


def test_partial_legacy_schema_stops_without_deleting_rows(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "partial.db"))
    with engine.begin() as c:
        c.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        c.exec_driver_sql("INSERT INTO users(id) VALUES (99)")
    with pytest.raises(RuntimeError, match="Partial legacy schema"):
        upgrade_database(engine)
    with engine.connect() as c:
        assert c.execute(text("SELECT id FROM users")).scalar() == 99
    engine.dispose()


def test_duplicate_learning_rows_require_operator_review(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "duplicates.db"))
    baseline(engine)
    with engine.begin() as c:
        c.exec_driver_sql(
            "INSERT INTO users(id,email,password_hash,full_name,role,is_active,created_at) VALUES (1,'demo@example.test','hash','Synthetic','EMPLOYEE',1,CURRENT_TIMESTAMP)"
        )
        c.exec_driver_sql(
            "INSERT INTO courses(id,code,title,category,description,duration_minutes,is_mandatory,total_lessons,cover_gradient,created_at) VALUES (1,'C1','Demo','Demo','Demo',1,1,1,'green',CURRENT_TIMESTAMP)"
        )
        for i in [1, 2]:
            c.execute(
                text(
                    "INSERT INTO enrollments(id,user_id,course_id,status,progress_percent,updated_at) VALUES (:i,1,1,'NOT_STARTED',0,CURRENT_TIMESTAMP)"
                ),
                {"i": i},
            )
    with pytest.raises(RuntimeError, match="Duplicate enrollments"):
        upgrade_database(engine)
    with engine.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM enrollments")).scalar() == 2
    assert "auth_sessions" not in inspect(engine).get_table_names()
    engine.dispose()


def test_unmigrated_database_is_rejected(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "old.db"))
    with pytest.raises(RuntimeError, match="python -m app.migrate"):
        require_current_schema(engine)
    engine.dispose()


def test_revision_migration_retains_approved_sources(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "approved.db"))
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0002_sessions_and_approvals")
        connection.exec_driver_sql(
            "INSERT INTO knowledge_documents(id,title,category,version,is_active,is_approved,is_synthetic,created_at,updated_at) VALUES (1,'Synthetic reviewed source','HR','2.0',1,1,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
    upgrade_database(engine)
    with engine.connect() as connection:
        row = connection.exec_driver_sql(
            "SELECT title,version,is_approved,is_synthetic,revision FROM knowledge_documents WHERE id=1"
        ).one()
        assert tuple(row) == ("Synthetic reviewed source", "2.0", 1, 1, 1)
    engine.dispose()
