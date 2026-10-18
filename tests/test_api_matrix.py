"""Every documented operation gets an actual HTTP success and authentication check."""

import pytest

from app.main import app
from tests.conftest import login
from tests.test_integration_gateway import approve_vacation, connected, gateway_client

__all__ = ["connected", "gateway_client"]

OPERATIONS = [
    ("GET", "/api/v1/config", None, 200, "public"),
    (
        "POST",
        "/api/v1/auth/login",
        {"email": "aruzhan@janapost.kz", "password": "Password123!"},
        200,
        "public",
    ),
    ("POST", "/api/v1/auth/logout", None, 200, "employee"),
    ("GET", "/api/v1/me", None, 200, "employee"),
    ("GET", "/api/v1/me/profile", None, 200, "employee"),
    ("GET", "/api/v1/me/dashboard", None, 200, "employee"),
    ("GET", "/api/v1/requests", None, 200, "employee"),
    (
        "POST",
        "/api/v1/requests",
        {"type": "Vacation", "start_date": "2027-01-11", "end_date": "2027-01-12"},
        201,
        "employee",
    ),
    ("GET", "/api/v1/requests/leave-calendar", None, 200, "employee"),
    ("GET", "/api/v1/requests/{request_id}", None, 200, "employee"),
    (
        "POST",
        "/api/v1/requests/{request_id}/approve",
        {"comment": "Synthetic review"},
        200,
        "manager",
    ),
    (
        "POST",
        "/api/v1/requests/{request_id}/reject",
        {"comment": "Synthetic review"},
        200,
        "manager",
    ),
    ("GET", "/api/v1/courses", None, 200, "employee"),
    ("POST", "/api/v1/courses/{course_id}/enroll", None, 200, "employee"),
    ("GET", "/api/v1/courses/{course_id}", None, 200, "employee"),
    ("GET", "/api/v1/courses/lessons/{lesson_id}", None, 200, "employee"),
    ("POST", "/api/v1/courses/lessons/{lesson_id}/quiz", {"answer_index": 0}, 200, "employee"),
    ("GET", "/api/v1/notifications", None, 200, "employee"),
    ("PATCH", "/api/v1/notifications/{notification_id}", {"is_read": True}, 200, "employee"),
    ("POST", "/api/v1/notifications/read-all", None, 200, "employee"),
    ("GET", "/api/v1/notifications/unread-count", None, 200, "employee"),
    ("POST", "/api/v1/ai/chat", {"question": "How do I request vacation?"}, 200, "employee"),
    ("GET", "/api/v1/ai/suggestions", None, 200, "employee"),
    ("GET", "/api/v1/ai/sources/{chunk_id}", None, 200, "employee"),
    ("GET", "/api/v1/ai/documents", None, 200, "employee"),
    ("GET", "/api/v1/manager/requests", None, 200, "manager"),
    ("GET", "/api/v1/manager/team", None, 200, "manager"),
    ("GET", "/api/v1/manager/team/{user_id}", None, 200, "manager"),
    ("GET", "/api/v1/admin/knowledge/documents", None, 200, "hr_admin"),
    (
        "POST",
        "/api/v1/admin/knowledge/documents",
        {"title": "Synthetic matrix document", "is_synthetic": True},
        201,
        "hr_admin",
    ),
    (
        "PATCH",
        "/api/v1/admin/knowledge/documents/{document_id}",
        {"title": "Synthetic renamed document"},
        200,
        "hr_admin",
    ),
    ("GET", "/api/v1/admin/knowledge", None, 200, "hr_admin"),
    (
        "POST",
        "/api/v1/admin/knowledge",
        {
            "document_id": 1,
            "section_title": "Synthetic matrix section",
            "content": "Synthetic matrix content.",
        },
        201,
        "hr_admin",
    ),
    (
        "PATCH",
        "/api/v1/admin/knowledge/{chunk_id}",
        {"content": "Synthetic changed content."},
        200,
        "hr_admin",
    ),
    ("POST", "/api/v1/admin/enrollments", {"user_id": 3, "course_id": 1}, 200, "hr_admin"),
    ("GET", "/api/v1/admin/integrations", None, 200, "hr_admin"),
    ("POST", "/api/v1/admin/integrations/refresh", None, 200, "hr_admin"),
    ("GET", "/api/v1/admin/integrations/queue", None, 200, "hr_admin"),
    ("GET", "/api/v1/admin/integrations/reviews", None, 200, "hr_admin"),
    (
        "POST",
        "/api/v1/admin/integrations/queue/{task_id}/retry",
        {"expected_retry_count": 0, "reason": "Synthetic outage resolved"},
        200,
        "hr_admin",
    ),
    (
        "POST",
        "/api/v1/admin/integrations/reviews/{employee_code}/resolve",
        {
            "observed_at": "2026-10-15T00:00:00Z",
            "user_id": 1,
            "reason": "Verified synthetic mapping",
        },
        200,
        "hr_admin",
    ),
    ("GET", "/api/v1/admin/audit", None, 200, "hr_admin"),
    ("GET", "/api/v1/admin/summary", None, 200, "hr_admin"),
    ("GET", "/health", None, 200, "public"),
    ("GET", "/", None, 200, "public"),
]

IDS = {
    "task_id": 1,
    "employee_code": "DEMO-MGR-001",
    "request_id": 1,
    "course_id": 1,
    "lesson_id": 1,
    "notification_id": 1,
    "chunk_id": 1,
    "document_id": 1,
    "user_id": 1,
}
PROTECTED = [case for case in OPERATIONS if case[4] != "public"]
QUERY = {"/api/v1/requests/leave-calendar": "?start_date=2027-01-11&end_date=2027-01-24"}


def case_name(case):
    return case[0] + " " + case[1]


def test_matrix_covers_every_openapi_operation():
    actual = {
        (method.upper(), path)
        for path, methods in app.openapi()["paths"].items()
        for method in methods
        if method in {"get", "post", "patch", "put", "delete"}
    }
    assert actual == {(case[0], case[1]) for case in OPERATIONS}


def test_exported_openapi_matches_application():
    import json
    from pathlib import Path

    exported = json.loads((Path(__file__).resolve().parents[1] / "docs/openapi.json").read_text())
    assert exported == app.openapi()


@pytest.mark.parametrize("case", OPERATIONS, ids=case_name)
def test_each_operation_has_a_working_authorized_request(client, case, request, db_session):
    method, path, payload, expected, role = case
    headers = {}
    ids = dict(IDS)
    if role != "public":
        email = {"employee": "aruzhan", "manager": "timur", "hr_admin": "aigerim"}[
            role
        ] + "@janapost.kz"
        headers = {"Authorization": "Bearer " + login(client, email)}
    if "{request_id}" in path:
        owner = (
            headers
            if role == "employee"
            else {"Authorization": "Bearer " + login(client, "aruzhan@janapost.kz")}
        )
        created = client.post(
            "/api/v1/requests", headers=owner, json={"type": "Vacation", "start_date": "2027-01-11"}
        )
        assert created.status_code == 201
        ids["request_id"] = created.json()["id"]
    if "{notification_id}" in path:
        ids["notification_id"] = client.get("/api/v1/notifications", headers=headers).json()[0][
            "id"
        ]
    if "{user_id}" in path:
        ids["user_id"] = client.get("/api/v1/manager/team", headers=headers).json()[0]["user_id"]
    if "{task_id}" in path:
        from app.integrations import outbox
        from app.models.integration import IntegrationOutbox

        request.getfixturevalue("connected")
        owner = {"Authorization": "Bearer " + login(client, "aruzhan@janapost.kz")}
        manager = {"Authorization": "Bearer " + login(client, "timur@janapost.kz")}
        approve_vacation(client, owner, manager)
        outbox.dispatch_one(db_session)
        task = db_session.query(IntegrationOutbox).one()
        task.status = "DEAD"
        db_session.commit()
        ids["task_id"] = task.id
    if "{employee_code}" in path:
        from app.integrations import profile_sync

        request.getfixturevalue("connected")
        profile_sync.sync_profiles(db_session, force=True)
        reviews = client.get("/api/v1/admin/integrations/reviews", headers=headers).json()
        review = next(r for r in reviews if r["employee_code"] == ids["employee_code"])
        payload = {**payload, "observed_at": review["observed_at"]}
    url = path.format(**ids) + QUERY.get(path, "")
    response = client.request(method, url, headers=headers, json=payload)
    assert response.status_code == expected, response.text
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Request-ID"]
    assert "password_hash" not in response.text


@pytest.mark.parametrize("case", PROTECTED, ids=case_name)
def test_every_protected_operation_rejects_anonymous_access(client, case):
    method, path, payload, _, _ = case
    response = client.request(method, path.format(**IDS) + QUERY.get(path, ""), json=payload)
    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"] == "unauthenticated"
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("role", ["employee", "manager"])
def test_all_administrative_operations_check_role(client, role):
    token = login(client, {"employee": "aruzhan@janapost.kz", "manager": "timur@janapost.kz"}[role])
    headers = {"Authorization": "Bearer " + token}
    failures = []
    for method, path, payload, _, required in PROTECTED:
        if required == "hr_admin" or (role == "employee" and path.startswith("/api/v1/manager/")):
            response = client.request(method, path.format(**IDS), headers=headers, json=payload)
            if response.status_code != 403:
                failures.append((method, path, response.status_code))
    assert not failures


@pytest.mark.parametrize("kind", ["revoked", "malformed", "deactivated"])
def test_all_protected_operations_reject_invalid_sessions(client, db_session, kind):
    from app.models.user import User

    token = login(client, "aigerim@janapost.kz")
    headers = {"Authorization": "Bearer " + token}
    if kind == "revoked":
        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    elif kind == "malformed":
        headers["Authorization"] = "Bearer definitely-not-a-jwt"
    else:
        user = db_session.query(User).filter_by(email="aigerim@janapost.kz").one()
        user.is_active = False
        db_session.commit()
    failures = []
    for method, path, payload, _, _ in PROTECTED:
        response = client.request(method, path.format(**IDS), headers=headers, json=payload)
        if response.status_code != 401:
            failures.append((method, path, response.status_code))
    assert not failures


@pytest.mark.parametrize(
    "case",
    [
        case
        for case in OPERATIONS
        if case[2] is not None and not case[1].endswith(("/approve", "/reject"))
    ],
    ids=case_name,
)
@pytest.mark.parametrize("body", ["missing", "invalid_json", "unknown_fields"])
def test_body_contracts_reject_missing_malformed_and_extra_input(
    client, hr_admin_headers, case, body
):
    method, path, payload, _, _ = case
    options = {"headers": hr_admin_headers}
    if body == "invalid_json":
        options["content"] = b'{"broken":'
        options["headers"] = {**hr_admin_headers, "Content-Type": "application/json"}
    elif body == "unknown_fields":
        options["json"] = {**payload, "unexpected": "private input"}
    response = client.request(method, path.format(**IDS), **options)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "validation_error"
    assert "private input" not in response.text
