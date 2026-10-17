"""Jury feedback: managers and HR must see employee HR cards with leave figures, in scope only.

Seed: Timur manages Aruzhan, Dana and Ruslan. Aruzhan has 18.5 days, an approved 2-day
vacation (REQ-1024) and a pending 5-day vacation (REQ-1042, 26–30 Oct).
"""

from app.models.user import User


def uid(db_session, email):
    return db_session.query(User).filter_by(email=email).one().id


def test_employee_cannot_open_directory(client, employee_headers, db_session):
    assert client.get("/api/v1/manager/team", headers=employee_headers).status_code == 403
    other = uid(db_session, "dana@janapost.kz")
    assert client.get(f"/api/v1/manager/team/{other}", headers=employee_headers).status_code == 403


def test_manager_sees_only_direct_reports_with_leave_figures(client, manager_headers):
    team = client.get("/api/v1/manager/team", headers=manager_headers).json()
    names = {m["full_name"] for m in team}
    assert names == {"Aruzhan Sadykova", "Dana Maratova", "Ruslan Aliyev"}
    aruzhan = next(m for m in team if m["full_name"] == "Aruzhan Sadykova")
    assert aruzhan["company"] and aruzhan["manager_name"] == "Timur Kasymov"
    assert (aruzhan["leave_balance_days"], aruzhan["used_days"]) == (18.5, 2.0)
    assert (aruzhan["pending_days"], aruzhan["available_days"]) == (5.0, 13.5)


def test_manager_opens_team_member_card_but_not_others(client, manager_headers, db_session):
    aruzhan = uid(db_session, "aruzhan@janapost.kz")
    card = client.get(f"/api/v1/manager/team/{aruzhan}", headers=manager_headers).json()
    assert card["location"] and card["position"]
    codes = {r["request_code"] for r in card["requests"]}
    assert {"REQ-1042", "REQ-1024"} <= codes
    assert (
        next(r for r in card["requests"] if r["request_code"] == "REQ-1042")["vacation_days"] == 5
    )
    assert card["courses"] and all(c["assigned"] for c in card["courses"])
    hr = uid(db_session, "aigerim@janapost.kz")
    outside = client.get(f"/api/v1/manager/team/{hr}", headers=manager_headers)
    assert outside.status_code == 404
    missing = client.get("/api/v1/manager/team/999999", headers=manager_headers)
    assert missing.json()["error"]["message"] == outside.json()["error"]["message"]


def test_hr_sees_every_employee(client, hr_admin_headers, db_session):
    team = client.get("/api/v1/manager/team", headers=hr_admin_headers).json()
    assert {"Aruzhan Sadykova", "Timur Kasymov", "Aigerim Nurlanova"} <= {
        m["full_name"] for m in team
    }
    timur = uid(db_session, "timur@janapost.kz")
    assert client.get(f"/api/v1/manager/team/{timur}", headers=hr_admin_headers).status_code == 200


def test_approval_moves_days_from_pending_to_used(client, manager_headers, db_session):
    aruzhan = uid(db_session, "aruzhan@janapost.kz")
    card = client.get(f"/api/v1/manager/team/{aruzhan}", headers=manager_headers).json()
    pending = next(r for r in card["requests"] if r["request_code"] == "REQ-1042")
    assert (
        client.post(f"/api/v1/requests/{pending['id']}/approve", headers=manager_headers, json={})
    ).status_code == 200
    after = client.get(f"/api/v1/manager/team/{aruzhan}", headers=manager_headers).json()
    assert (after["leave_balance_days"], after["used_days"]) == (13.5, 7.0)
    assert (after["pending_days"], after["available_days"]) == (0.0, 13.5)


def test_configured_excluded_dates_are_not_charged(
    client, employee_headers, manager_headers, monkeypatch
):
    from datetime import date

    from app.config import settings

    monkeypatch.setattr(
        settings,
        "LEAVE_EXCLUDED_DATES",
        [date(2026, 12, 16), date(2027, 3, 21), date(2027, 3, 22), date(2027, 3, 23)],
    )
    # 14–18 Dec 2026 contains Independence Day (16 Dec): 5 calendar days, 4 charged.
    created = client.post(
        "/api/v1/requests",
        headers=employee_headers,
        json={"type": "Vacation", "start_date": "2026-12-14", "end_date": "2026-12-18"},
    ).json()
    assert created["vacation_days"] == 4
    client.post(f"/api/v1/requests/{created['id']}/approve", headers=manager_headers, json={})
    profile = client.get("/api/v1/me/profile", headers=employee_headers).json()
    assert profile["leave_balance_days"] == 14.5
    only_holidays = client.post(
        "/api/v1/requests",
        headers=employee_headers,
        json={"type": "Vacation", "start_date": "2027-03-21", "end_date": "2027-03-23"},
    )
    assert only_holidays.status_code == 422
