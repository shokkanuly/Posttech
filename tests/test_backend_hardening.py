"""Regression checks for malformed API input and concurrent knowledge review."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException

from app.migrate import SchemaNotCurrentError
from app.services.auth_service import LoginLimiter


def reviewed_document(client, headers, document_id=1):
    return next(
        d
        for d in client.get("/api/v1/admin/knowledge/documents", headers=headers).json()
        if d["id"] == document_id
    )


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("GET", "/requests/{id}", None),
        ("POST", "/requests/{id}/approve", {}),
        ("POST", "/requests/{id}/reject", {}),
        ("GET", "/courses/{id}", None),
        ("POST", "/courses/{id}/enroll", None),
        ("GET", "/courses/lessons/{id}", None),
        ("POST", "/courses/lessons/{id}/quiz", {"answer_index": 0}),
        ("PATCH", "/notifications/{id}", {"is_read": True}),
        ("GET", "/ai/sources/{id}", None),
        ("PATCH", "/admin/knowledge/documents/{id}", {"title": "Synthetic"}),
        ("PATCH", "/admin/knowledge/{id}", {"content": "Synthetic"}),
    ],
)
def test_oversized_identifiers_are_validation_errors(
    client, hr_admin_headers, method, path, payload
):
    response = client.request(
        method, "/api/v1" + path.format(id=2**63), headers=hr_admin_headers, json=payload
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize("value", ["false", "true", 1, 0])
def test_knowledge_approval_requires_json_boolean(client, hr_admin_headers, value):
    response = client.patch(
        "/api/v1/admin/knowledge/documents/1",
        headers=hr_admin_headers,
        json={"is_approved": value},
    )
    assert response.status_code == 422


def test_stale_document_cannot_be_approved(client, hr_admin_headers):
    documents = client.get("/api/v1/admin/knowledge/documents", headers=hr_admin_headers).json()
    document = documents[0]
    chunks = client.get("/api/v1/admin/knowledge", headers=hr_admin_headers).json()
    chunk = next(c for c in chunks if c["document_id"] == document["id"])
    changed = client.patch(
        f"/api/v1/admin/knowledge/{chunk['id']}",
        headers=hr_admin_headers,
        json={"content": "New synthetic content the reviewer has not seen."},
    )
    assert changed.status_code == 200
    response = client.patch(
        f"/api/v1/admin/knowledge/documents/{document['id']}",
        headers=hr_admin_headers,
        json={"is_approved": True, "expected_revision": document["revision"]},
    )
    assert response.status_code == 409
    current = client.get("/api/v1/admin/knowledge/documents", headers=hr_admin_headers).json()[0]
    assert current["is_approved"] is False


def test_oversized_json_body_is_rejected_before_parsing(client):
    response = client.post(
        "/api/v1/auth/login",
        content=b'{"password":"' + b"x" * (256 * 1024) + b'"}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.headers["Cache-Control"] == "no-store"
    assert "x" * 100 not in response.text


@pytest.mark.parametrize("value", [2**63, 0, -1, True, 1.0, "1"])
def test_body_identifiers_are_strict_bounded_integers(client, hr_admin_headers, value):
    response = client.post(
        "/api/v1/admin/enrollments",
        headers=hr_admin_headers,
        json={"user_id": value, "course_id": 1},
    )
    assert response.status_code == 422
    response = client.post(
        "/api/v1/admin/knowledge",
        headers=hr_admin_headers,
        json={"document_id": value, "section_title": "Synthetic", "content": "Synthetic"},
    )
    assert response.status_code == 422


def test_approval_requires_review_revision(client, hr_admin_headers):
    response = client.patch(
        "/api/v1/admin/knowledge/documents/1", headers=hr_admin_headers, json={"is_approved": True}
    )
    assert response.status_code == 422


def test_concurrent_approval_and_edit_have_one_winner(client, hr_admin_headers):
    doc = reviewed_document(client, hr_admin_headers)
    changes = [
        (
            "/admin/knowledge/documents/1",
            {"is_approved": True, "expected_revision": doc["revision"]},
        ),
        (
            "/admin/knowledge/1",
            {"content": "Synthetic changed source.", "expected_revision": doc["revision"]},
        ),
    ]
    with ThreadPoolExecutor(2) as pool:
        responses = list(
            pool.map(
                lambda change: client.patch(
                    "/api/v1" + change[0], headers=hr_admin_headers, json=change[1]
                ),
                changes,
            )
        )
    assert sorted(r.status_code for r in responses) == [200, 409]
    current = reviewed_document(client, hr_admin_headers)
    assert current["revision"] == doc["revision"] + 1
    source = client.get("/api/v1/ai/sources/1", headers=hr_admin_headers)
    if responses[0].status_code == 200:
        assert current["is_approved"] is True
        assert source.status_code == 200
        assert source.json()["content"] != changes[1][1]["content"]
    else:
        assert current["is_approved"] is False
        assert source.status_code == 404


def test_citation_rejects_changed_source_after_reapproval(client, hr_admin_headers):
    original = client.get("/api/v1/ai/sources/1", headers=hr_admin_headers).json()
    response = client.patch(
        "/api/v1/admin/knowledge/1",
        headers=hr_admin_headers,
        json={"content": "Synthetic revised source."},
    )
    assert response.status_code == 200
    revision = response.json()["document_revision"]
    assert (
        client.patch(
            "/api/v1/admin/knowledge/documents/1",
            headers=hr_admin_headers,
            json={"is_approved": True, "expected_revision": revision},
        ).status_code
        == 200
    )
    url = "/api/v1/ai/sources/1?revision=" + str(original["document_revision"])
    assert client.get(url, headers=hr_admin_headers).status_code == 409
    current = client.get("/api/v1/ai/sources/1", headers=hr_admin_headers).json()
    assert (
        client.get(
            "/api/v1/ai/sources/1?revision=" + str(current["document_revision"]),
            headers=hr_admin_headers,
        ).status_code
        == 200
    )


def test_chunked_request_body_is_bounded_without_content_length(client):
    def chunks():
        for _ in range(5):
            yield b"x" * 65536

    response = client.post(
        "/api/v1/ai/chat", content=chunks(), headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


@pytest.mark.parametrize("length", ["-1", "letters", "9" * 100])
def test_invalid_content_length_is_rejected(client, length):
    response = client.post("/api/v1/auth/login", content=b"{}", headers={"Content-Length": length})
    assert response.status_code == 400


def test_unexpected_error_is_redacted_and_not_cached(client, employee_headers, monkeypatch, caplog):
    from app.services.notification_service import notification_service

    def fail(*args, **kwargs):
        raise RuntimeError("private employee data; password=never-log-this")

    monkeypatch.setattr(notification_service, "get_unread_count", fail)
    response = client.get("/api/v1/notifications/unread-count", headers=employee_headers)
    assert response.status_code == 500
    assert "private employee" not in response.text + caplog.text
    assert "never-log-this" not in response.text + caplog.text
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_health_returns_503_for_outdated_schema(client, monkeypatch):
    import app.main as main

    def not_ready(*args):
        raise SchemaNotCurrentError("internal schema information")

    monkeypatch.setattr(main, "require_current_schema", not_ready)
    response = client.get("/health")
    assert response.status_code == 503
    assert "internal schema information" not in response.text


def test_login_limiter_counts_inflight_attempts():
    limiter = LoginLimiter()
    keys = [limiter.check("synthetic-ip") for _ in range(5)]
    with pytest.raises(HTTPException) as error:
        limiter.check("synthetic-ip")
    assert error.value.status_code == 429
    limiter.finish(keys.pop(), failed=False)
    replacement = limiter.check("synthetic-ip")
    for key in [*keys, replacement]:
        limiter.finish(key, failed=True)
    assert not limiter.inflight
    with pytest.raises(HTTPException):
        limiter.check("synthetic-ip")


def test_zero_lifetime_token_expires_instead_of_using_default(client, db_session):
    from datetime import timedelta

    from app.services.auth_service import auth_service

    token = auth_service.create_access_token(3, db_session, timedelta(0))
    db_session.commit()
    assert client.get("/api/v1/me", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_failed_knowledge_edit_rolls_back_revision(client, hr_admin_headers, monkeypatch):
    from sqlalchemy.exc import OperationalError

    from app.services.audit_service import audit_service

    before = reviewed_document(client, hr_admin_headers)

    def fail(*args, **kwargs):
        raise OperationalError("sensitive SQL", {}, Exception("private data"))

    monkeypatch.setattr(audit_service, "log_event", fail)
    response = client.patch(
        "/api/v1/admin/knowledge/1",
        headers=hr_admin_headers,
        json={"content": "Synthetic failed edit."},
    )
    assert response.status_code == 503
    assert "sensitive SQL" not in response.text
    assert reviewed_document(client, hr_admin_headers) == before


COLLECTIONS = [
    "/requests",
    "/manager/requests",
    "/manager/team",
    "/courses",
    "/notifications",
    "/admin/knowledge",
    "/admin/knowledge/documents",
    "/admin/audit",
    "/ai/documents",
]


@pytest.mark.parametrize("path", COLLECTIONS)
def test_collections_have_stable_pagination(client, hr_admin_headers, path):
    expected = client.get("/api/v1" + path + "?limit=100", headers=hr_admin_headers).json()
    actual = []
    for offset in range(len(expected) + 1):
        response = client.get(
            "/api/v1" + path + f"?limit=1&offset={offset}", headers=hr_admin_headers
        )
        assert response.status_code == 200
        page = response.json()
        assert len(page) <= 1
        actual.extend(page)
    assert actual == expected


@pytest.mark.parametrize(
    "query", ["limit=0", "limit=101", "offset=-1", "offset=1000001", "offset=abc"]
)
def test_all_collections_enforce_pagination_bounds(client, hr_admin_headers, query):
    for path in COLLECTIONS:
        response = client.get("/api/v1" + path + "?" + query, headers=hr_admin_headers)
        assert response.status_code == 422, (path, response.text)


@pytest.mark.parametrize("manager_state", ["missing", "inactive", "wrong_role"])
def test_unavailable_manager_routes_notification_to_hr(
    client, employee_headers, db_session, manager_state
):
    from app.models.enums import UserRole
    from app.models.notification import Notification
    from app.models.profile import EmployeeProfile
    from app.models.user import User

    if manager_state == "missing":
        db_session.query(EmployeeProfile).filter_by(user_id=3).one().manager_id = None
    else:
        manager = db_session.get(User, 1)
        if manager_state == "inactive":
            manager.is_active = False
        else:
            manager.role = UserRole.EMPLOYEE
    db_session.commit()
    response = client.post(
        "/api/v1/requests",
        headers=employee_headers,
        json={"type": "Vacation", "start_date": "2027-01-01"},
    )
    assert response.status_code == 201
    code = response.json()["request_code"]
    notifications = db_session.query(Notification).filter_by(reference_id=code).all()
    assert {n.user_id for n in notifications} == {2, 3}
    own = next(n for n in notifications if n.user_id == 3)
    assert "sent to HR" in own.message


def test_course_catalog_uses_bounded_queries(db_session, db_engine):
    from sqlalchemy import event

    from app.models.user import User
    from app.services.academy_service import academy_service

    user = db_session.get(User, 3)
    queries = []

    def count_query(_connection, _cursor, statement, *_args):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append(statement)

    event.listen(db_engine, "before_cursor_execute", count_query)
    try:
        courses = academy_service.get_user_courses(db_session, user)
        assert len(courses) == 2
        assert len(queries) <= 3
    finally:
        event.remove(db_engine, "before_cursor_execute", count_query)
