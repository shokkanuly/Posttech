"""Gemini is optional and never trusted: every model answer must be backed by its sources."""

import pytest

from app.config import settings
from app.integrations import gemini
from app.services.ai_service import AIService

QUESTION = "How do I request vacation in the system?"


@pytest.fixture
def gemini_on(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key-not-real")


def fake_model(monkeypatch, build):
    calls = []

    def fake(question, passages, language):
        calls.append((question, passages, language))
        return build(passages)

    monkeypatch.setattr(gemini, "generate_grounded_answer", fake)
    return calls


def ask(client, headers, question=QUESTION):
    result = client.post("/api/v1/ai/chat", headers=headers, json={"question": question})
    assert result.status_code == 200, result.text
    return result.json()


def test_verified_model_answer_is_shown_with_its_sources(
    client, employee_headers, gemini_on, monkeypatch
):
    calls = fake_model(
        monkeypatch,
        lambda passages: {
            "answerable": True,
            "answer": passages[0]["text"][:60],
            "source_ids": ["S1"],
            "quotes": [passages[0]["text"][:60]],
        },
    )
    data = ask(client, employee_headers)
    assert data["answer_status"] == "grounded"
    assert data["engine"] == f"gemini:{settings.GEMINI_MODEL}"
    assert calls[0][1][0]["text"][:60] in data["answer"]
    assert len(data["sources"]) == 1 and data["sources"][0]["relevance"] > 0
    # Only approved passages and the question are sent — no employee records.
    question, passages, _language = calls[0]
    assert question == QUESTION
    assert all(set(p) == {"id", "title", "text", "evidence", "chunk"} for p in passages)


@pytest.mark.parametrize(
    "tamper",
    [
        lambda p: {"answer": "You get 99 vacation days.", "quotes": [p[0]["text"][:60]]},
        lambda p: {"source_ids": ["S9"]},
        lambda p: {"quotes": ["this sentence is not in any approved source"]},
        lambda p: {"answer": "Write to boss@example.com.", "quotes": [p[0]["text"][:60]]},
        lambda p: {"answerable": False},
    ],
    ids=["invented-number", "unknown-source", "fake-quote", "invented-email", "not-answerable"],
)
def test_unverified_model_answer_falls_back_to_source_text(
    client, employee_headers, gemini_on, monkeypatch, tamper
):
    def build(passages):
        answer = {
            "answerable": True,
            "answer": "Open My requests and select Vacation.",
            "source_ids": ["S1"],
            "quotes": [passages[0]["text"][:60]],
        }
        return answer | tamper(passages)

    fake_model(monkeypatch, build)
    data = ask(client, employee_headers)
    assert data["engine"] == "extractive"
    assert data["answer_status"] == "grounded"  # the strict extractive match still answers
    assert "99" not in data["answer"] and "boss@example.com" not in data["answer"]
    assert data["sources"]


def test_model_outage_keeps_extractive_answers(client, employee_headers, gemini_on, monkeypatch):
    fake_model(monkeypatch, lambda passages: None)
    data = ask(client, employee_headers)
    assert data["answer_status"] == "grounded" and data["engine"] == "extractive"


def test_private_questions_never_reach_the_model(client, employee_headers, gemini_on, monkeypatch):
    def forbidden(*_args):
        raise AssertionError("private question was sent to the model")

    monkeypatch.setattr(gemini, "generate_grounded_answer", forbidden)
    data = ask(client, employee_headers, "What is the salary of Timur?")
    assert data["answer_status"] == "unauthorized" and data["sources"] == []


def test_out_of_scope_question_stays_a_safe_fallback(
    client, employee_headers, gemini_on, monkeypatch
):
    fake_model(
        monkeypatch,
        lambda passages: {"answerable": False, "answer": "", "source_ids": [], "quotes": []},
    )
    data = ask(client, employee_headers, "What is the pet insurance reimbursement policy?")
    assert data["answer_status"] == "fallback" and data["sources"] == []
    assert "hr-support@janapost.kz" in data["escalation_guidance"]


def test_gemini_is_off_without_key(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    assert not gemini.enabled()


def test_verifier_checks_quotes_numbers_and_ids():
    passages = [
        {
            "id": "S1",
            "text": "Approved amounts are disbursed on the 20th of the month.",
            "chunk": "c1",
        }
    ]
    good = {
        "answerable": True,
        "answer": "disbursed on the 20th of the month",
        "source_ids": ["S1"],
        "quotes": ["disbursed on the 20th of the month"],
    }
    assert AIService.verify_llm_answer(good, passages) == (
        "disbursed on the 20th of the month",
        ["c1"],
    )
    assert (
        AIService.verify_llm_answer(good | {"answer": "It is paid on the 25th."}, passages) is None
    )
    assert AIService.verify_llm_answer(good | {"quotes": ["short"]}, passages) is None
    assert AIService.verify_llm_answer("not json", passages) is None


@pytest.mark.parametrize(
    "question,language",
    [("Как получить аванс из зарплаты?", "ru-RU"), ("Жалақы авансын қалай аламын?", "kk-KZ")],
)
def test_advance_questions_are_not_mistaken_for_privacy(
    client, employee_headers, question, language
):
    headers = {**employee_headers, "Accept-Language": language}
    data = ask(client, headers, question)
    assert data["answer_status"] != "unauthorized"
