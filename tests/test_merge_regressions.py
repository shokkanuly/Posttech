"""Regression tests for defects found while integrating the two local worktrees."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date

import httpx
import pytest

from app.integrations import gemini
from app.integrations.one_c_zup import one_c_adapter
from app.services.ai_service import AIService


@pytest.mark.parametrize("ids", [[{}], [[]], ["S1", "S1"], [None], "S1"])
def test_untrusted_model_source_ids_never_crash(ids):
    passages = [{"id": "S1", "text": "You must submit a vacation request.", "chunk": "c1"}]
    result = {
        "answerable": True,
        "answer": passages[0]["text"],
        "source_ids": ids,
        "quotes": [passages[0]["text"]],
    }
    assert AIService.verify_llm_answer(result, passages) is None


def test_valid_quote_does_not_authorize_fabricated_claim():
    text = "You must submit a vacation request."
    passages = [{"id": "S1", "text": text, "chunk": "c1"}]
    result = {
        "answerable": True,
        "answer": "All employees are fired immediately.",
        "source_ids": ["S1"],
        "quotes": [text],
    }
    assert AIService.verify_llm_answer(result, passages) is None


def test_cross_language_evidence_cannot_back_displayed_quote():
    passages = [
        {
            "id": "S1",
            "text": "Подайте заявку на отпуск.",
            "evidence": "You are granted unlimited vacation.",
            "chunk": "c1",
        }
    ]
    result = {
        "answerable": True,
        "answer": passages[0]["evidence"],
        "source_ids": ["S1"],
        "quotes": [passages[0]["evidence"]],
    }
    assert AIService.verify_llm_answer(result, passages) is None


def test_gemini_error_logs_are_redacted(monkeypatch, caplog):
    def fail(*args, **kwargs):
        raise httpx.ConnectError("private-question SECRET-KEY private-document")

    monkeypatch.setattr(httpx, "post", fail)
    assert gemini.generate_grounded_answer("private-question", [], "ru") is None
    assert "ConnectError" in caplog.text
    assert all(
        value not in caplog.text for value in ["private-question", "SECRET-KEY", "private-document"]
    )


def test_end_date_cannot_exceed_horizon(client, employee_headers):
    result = client.post(
        "/api/v1/requests",
        headers=employee_headers,
        json={"type": "Vacation", "start_date": "2026-12-01", "end_date": "9999-12-31"},
    )
    assert result.status_code == 422


def test_simultaneous_vacations_cannot_reserve_same_dates(client, employee_headers):
    def submit(_index):
        return client.post(
            "/api/v1/requests",
            headers=employee_headers,
            json={"type": "Vacation", "start_date": "2026-12-01", "end_date": "2026-12-04"},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(submit, range(2)))
    assert sorted(statuses) == [201, 409]


def test_simultaneous_different_vacations_cannot_overreserve(client, employee_headers):
    def submit(start):
        return client.post(
            "/api/v1/requests",
            headers=employee_headers,
            json={
                "type": "Vacation",
                "start_date": f"2026-12-{start:02}",
                "end_date": f"2026-12-{start + 7:02}",
            },
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(submit, [1, 20]))
    assert sorted(statuses) == [201, 400]


def test_calendar_excludes_public_holidays_without_configuration():
    # Independence Day (16 Dec) is built in, so an empty LEAVE_EXCLUDED_DATES cannot drop it.
    assert one_c_adapter.vacation_days(date(2026, 12, 14), date(2026, 12, 18)) == 4
    assert one_c_adapter.vacation_days(date(2026, 11, 23), date(2026, 11, 27)) == 5
