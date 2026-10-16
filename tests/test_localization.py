import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from starlette.requests import Request

from app.localization import current_language, language_for
from app.models.audit import AuditEvent
from app.models.knowledge import KnowledgeChunk
from app.models.user import User
from app.provision_demo import DEMO_ACCOUNTS, provision_accounts


@pytest.mark.parametrize(
    "language,name,title",
    [
        ("ru", "Аружан Садыкова", "Основы защиты данных"),
        ("kk", "Аружан Садықова", "Деректерді қорғау негіздері"),
    ],
)
def test_localized_profile_courses_and_lessons(client, employee_headers, language, name, title):
    headers = {**employee_headers, "Accept-Language": language}
    profile = client.get("/api/v1/me/profile", headers=headers)
    assert profile.status_code == 200
    assert profile.headers["Content-Language"] == language
    assert profile.json()["full_name"] == name
    assert profile.json()["courses"][0]["title"] == title
    lesson = client.get("/api/v1/courses/lessons/1", headers=headers).json()
    assert "Can you share" not in lesson["quiz_question"]
    assert "Postal communication" not in lesson["content_markdown"]
    assert all("Yes," not in answer and "No," not in answer for answer in lesson["quiz_options"])


@pytest.mark.parametrize(
    "language,question",
    [
        ("ru", "Как подать заявку на отпуск?"),
        ("kk", "Демалысқа қалай өтініш беремін?"),
        ("ru", "Где посмотреть остаток дней отпуска?"),
        ("kk", "Демалыс күндерінің қалдығын қайдан көремін?"),
        ("ru", "Как запросить аванс?"),
        ("kk", "Авансты қалай сұраймын?"),
        ("ru", "Какой график работы?"),
        ("kk", "Жұмыс кестесі қандай?"),
    ],
)
def test_ai_uses_stored_translated_sources(
    client, employee_headers, db_session, language, question
):
    headers = {**employee_headers, "Accept-Language": language}
    response = client.post("/api/v1/ai/chat", headers=headers, json={"question": question})
    assert response.status_code == 200, response.text
    answer = response.json()
    assert answer["answer_status"] == "grounded", answer
    assert "Synthetic example" not in answer["answer"]
    for citation in answer["sources"]:
        assert citation["language"] == language
        source = client.get(
            f"/api/v1/ai/sources/{citation['chunk_id']}?revision={citation['document_revision']}&language={language}",
            headers=headers,
        ).json()
        stored = db_session.get(KnowledgeChunk, citation["chunk_id"])
        assert source["content"] == stored.translations[language]["content"]
        assert source["content"] in answer["answer"]
        assert source["content"].startswith(citation["snippet"])
    event = (
        db_session.query(AuditEvent)
        .filter_by(action="AI_QUERY_GROUNDED_ANSWER")
        .order_by(AuditEvent.id.desc())
        .first()
    )
    reference = json.loads(event.details_json)["source_revisions"][0]
    stored = db_session.get(KnowledgeChunk, answer["sources"][0]["chunk_id"])
    assert (
        reference["content_hash"]
        == hashlib.sha256(stored.translations[language]["content"].encode()).hexdigest()
    )


@pytest.mark.parametrize(
    "language,question",
    [("ru", "Есть ли страховка домашних животных?"), ("kk", "Үй жануарларына сақтандыру бар ма?")],
)
def test_localized_fallback_and_errors(client, employee_headers, language, question):
    headers = {**employee_headers, "Accept-Language": language}
    answer = client.post("/api/v1/ai/chat", headers=headers, json={"question": question}).json()
    assert answer["answer_status"] == "fallback"
    assert answer["sources"] == []
    assert "couldn't find" not in answer["answer"]
    error = client.post("/api/v1/requests", headers=headers, json={}).json()
    assert error["error"]["code"] == "validation_error"
    assert all(field["message"] != "Field required" for field in error["error"]["fields"])
    denied = client.get("/api/v1/admin/summary", headers=headers)
    assert denied.status_code == 403
    assert "Access denied" not in denied.text


def test_locales_do_not_leak_between_simultaneous_requests(client, employee_headers):
    expected = {"en": "Aruzhan Sadykova", "ru": "Аружан Садыкова", "kk": "Аружан Садықова"}

    def read(language):
        result = client.get("/api/v1/me", headers={**employee_headers, "Accept-Language": language})
        assert result.json()["user"]["full_name"] == expected[language]

    with ThreadPoolExecutor(3) as pool:
        list(pool.map(read, ["ru", "en", "kk"] * 3))
    assert current_language.get() == "en"


def test_source_edit_removes_stale_translations(client, employee_headers, hr_admin_headers):
    response = client.patch(
        "/api/v1/admin/knowledge/1",
        headers=hr_admin_headers,
        json={"content": "A new source that has no reviewed translation."},
    )
    assert response.status_code == 200
    assert response.json()["translations"] == {}
    revision = response.json()["document_revision"]
    assert (
        client.patch(
            "/api/v1/admin/knowledge/documents/1",
            headers=hr_admin_headers,
            json={"is_approved": True, "expected_revision": revision},
        ).status_code
        == 200
    )
    assert (
        client.get("/api/v1/ai/sources/1?language=ru", headers=employee_headers).status_code == 404
    )
    assert (
        client.get("/api/v1/ai/sources/1?language=en", headers=employee_headers).status_code == 200
    )


def test_demo_accounts_are_created_sequentially_and_repeatably(client, db_session):
    accounts = provision_accounts(db_session)
    assert accounts["hr_admin"] < accounts["manager"] < accounts["employee"]
    employee = db_session.get(User, accounts["employee"])
    assert employee.profile.manager_id == accounts["manager"]
    original_hashes = {user.id: user.password_hash for user in db_session.query(User).all()}
    assert provision_accounts(db_session) == accounts
    assert {user.id: user.password_hash for user in db_session.query(User).all()} == original_hashes
    assert client.get("/api/v1/config").json()["demo_accounts"] == DEMO_ACCOUNTS
    headers = {}
    for role in ("hr_admin", "manager", "employee"):
        login = client.post(
            "/api/v1/auth/login", json={"email": DEMO_ACCOUNTS[role], "password": "Password123!"}
        )
        assert login.status_code == 200
        assert login.json()["user"]["role"] == role
        headers[role] = {"Authorization": "Bearer " + login.json()["access_token"]}
    assert client.get("/api/v1/admin/summary", headers=headers["employee"]).status_code == 403
    assert client.get("/api/v1/admin/summary", headers=headers["manager"]).status_code == 403
    assert client.get("/api/v1/admin/summary", headers=headers["hr_admin"]).status_code == 200
    team = client.get("/api/v1/manager/team", headers=headers["manager"]).json()
    assert [member["user_id"] for member in team] == [accounts["employee"]]


def test_demo_provisioning_is_forbidden_in_production(db_session, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    with pytest.raises(RuntimeError, match="non-production"):
        provision_accounts(db_session)


@pytest.mark.parametrize(
    "header,expected",
    [
        ("ru-RU", "ru"),
        ("kk-KZ", "kk"),
        ("kz", "kk"),
        ("ru;q=0.2,kk;q=0.9", "kk"),
        ("ru;q=0,en;q=1", "en"),
        ("unknown", "en"),
    ],
)
def test_language_negotiation(header, expected):
    assert (
        language_for(Request({"type": "http", "headers": [(b"accept-language", header.encode())]}))
        == expected
    )
