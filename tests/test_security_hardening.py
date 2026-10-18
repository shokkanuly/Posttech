"""Demo one-click sign-in, quiz answer secrecy and anti-framing headers."""

import pytest

from app.config import settings


@pytest.mark.parametrize("role", ["employee", "manager", "hr_admin"])
def test_demo_login_signs_in_as_the_demo_role(client, role):
    result = client.post("/api/v1/auth/demo-login", json={"role": role})
    assert result.status_code == 200, result.text
    session = result.json()
    assert session["user"]["role"] == role
    me = client.get("/api/v1/me", headers={"Authorization": "Bearer " + session["access_token"]})
    assert me.status_code == 200 and me.json()["user"]["role"] == role


def test_demo_login_rejects_other_roles_and_is_absent_outside_demo_mode(client, monkeypatch):
    for body in ({"role": "admin"}, {"role": "manager", "email": "x@example.com"}, {}):
        assert client.post("/api/v1/auth/demo-login", json=body).status_code == 422
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    assert client.post("/api/v1/auth/demo-login", json={"role": "manager"}).status_code == 404


def test_wrong_quiz_answer_does_not_reveal_the_right_one(client, employee_headers):
    lesson = client.get("/api/v1/courses/1", headers=employee_headers).json()["lessons"][-1]["id"]
    wrong = client.post(
        f"/api/v1/courses/lessons/{lesson}/quiz", headers=employee_headers, json={"answer_index": 1}
    ).json()
    assert wrong["passed"] is False and wrong["correct_index"] is None


def test_pages_cannot_be_framed_by_other_sites(client):
    response = client.get("/")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Content-Security-Policy"] == "frame-ancestors 'none'"
