"""Business rules found missing in review: dates, overlaps, reserved balance, advance cap.

"Today" is pinned to 2026-10-15 by conftest. Aruzhan starts with 18.5 days and a pending
5-day vacation (REQ-1042, 26–30 Oct), so 13.5 days are free to request.
"""

import pytest

from app.config import settings


def submit(client, headers, **payload):
    return client.post("/api/v1/requests", headers=headers, json=payload)


@pytest.mark.parametrize(
    "start,message",
    [
        ("2026-10-14", "Start date cannot be in the past"),
        ("2027-10-16", "Request dates exceed the configured planning horizon"),
    ],
)
def test_dates_must_be_from_today_to_one_year_ahead(client, employee_headers, start, message):
    result = submit(client, employee_headers, type="Advance payment", start_date=start, amount=1000)
    assert result.status_code == 422
    assert result.json()["error"]["message"] == message


def test_today_is_accepted(client, employee_headers):
    result = submit(
        client, employee_headers, type="Advance payment", start_date="2026-10-15", amount=1000
    )
    assert result.status_code == 201


def test_overlapping_vacations_are_rejected(client, employee_headers):
    first = submit(
        client, employee_headers, type="Vacation", start_date="2026-11-23", end_date="2026-11-25"
    )
    assert first.status_code == 201
    for start, end in [
        ("2026-11-23", "2026-11-25"),
        ("2026-11-25", "2026-11-27"),
        ("2026-11-20", "2026-11-23"),
    ]:
        overlap = submit(client, employee_headers, type="Vacation", start_date=start, end_date=end)
        assert overlap.status_code == 409, (start, end)
    adjacent = submit(
        client, employee_headers, type="Vacation", start_date="2026-11-26", end_date="2026-11-26"
    )
    assert adjacent.status_code == 201


def test_pending_days_are_reserved(client, employee_headers):
    too_many = submit(
        client, employee_headers, type="Vacation", start_date="2026-12-01", end_date="2026-12-14"
    )
    assert too_many.status_code == 400  # 14 days > 18.5 − 5 pending
    assert "13.5" in too_many.json()["error"]["message"]
    fits = submit(
        client, employee_headers, type="Vacation", start_date="2026-12-01", end_date="2026-12-13"
    )
    assert fits.status_code == 201


def test_rejected_requests_free_their_dates(client, employee_headers, manager_headers):
    first = submit(
        client, employee_headers, type="Vacation", start_date="2026-11-23", end_date="2026-11-24"
    ).json()
    reject = client.post(f"/api/v1/requests/{first['id']}/reject", headers=manager_headers, json={})
    assert reject.status_code == 200
    again = submit(
        client, employee_headers, type="Vacation", start_date="2026-11-23", end_date="2026-11-24"
    )
    assert again.status_code == 201


def test_advance_amount_is_capped(client, employee_headers):
    over = submit(
        client,
        employee_headers,
        type="Advance payment",
        start_date="2026-11-20",
        amount=settings.MAX_ADVANCE_AMOUNT + 0.01,
    )
    assert over.status_code == 422
    at_cap = submit(
        client,
        employee_headers,
        type="Advance payment",
        start_date="2026-11-20",
        amount=settings.MAX_ADVANCE_AMOUNT,
    )
    assert at_cap.status_code == 201


def test_rule_errors_are_localized(client, employee_headers):
    headers = {**employee_headers, "Accept-Language": "ru-RU"}
    result = submit(client, headers, type="Advance payment", start_date="2020-01-01", amount=1000)
    assert result.json()["error"]["message"] == "Дата начала не может быть в прошлом"
