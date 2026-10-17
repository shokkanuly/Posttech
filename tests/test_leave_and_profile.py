"""Leave calendar marking, approval-based profile updates and HR-only employee details."""

from datetime import date, timedelta


def me(client, headers):
    return client.get("/api/v1/me/profile", headers=headers).json()


def test_leave_calendar_marks_weekends_and_public_holidays(client, employee_headers):
    res = client.get(
        "/api/v1/requests/leave-calendar?start_date=2026-11-26&end_date=2027-01-21",
        headers=employee_headers,
    )
    assert res.status_code == 200, res.text
    cal = res.json()
    first, last = date(2026, 11, 26), date(2027, 1, 21)
    weekends = sum(
        (first + timedelta(days=i)).weekday() >= 5 for i in range((last - first).days + 1)
    )
    assert len(cal["days"]) == 57 and cal["holiday_days"] == 3
    # 2 Jan 2027 is a Saturday and a holiday: the holiday wins, so it is not charged.
    assert cal["weekend_days"] == weekends - 1 and cal["charged_days"] == 54
    holidays = {d["day"]: d["holiday"] for d in cal["days"] if d["kind"] == "holiday"}
    assert holidays == {
        "2026-12-16": "Independence Day",
        "2027-01-01": "New Year",
        "2027-01-02": "New Year",
    }
    assert cal["days"][2] == {"day": "2026-11-28", "kind": "weekend", "holiday": None}
    assert 0 <= cal["available_days"] <= me(client, employee_headers)["leave_balance_days"]
    backwards = client.get(
        "/api/v1/requests/leave-calendar?start_date=2026-12-10&end_date=2026-12-01",
        headers=employee_headers,
    )
    assert backwards.status_code == 422


def test_vacation_details_show_the_charged_day_breakdown(client, employee_headers):
    created = client.post(
        "/api/v1/requests",
        headers=employee_headers,
        json={"type": "Vacation", "start_date": "2026-12-14", "end_date": "2026-12-20"},
    ).json()
    # 7 calendar days: Sat/Sun charged, 16 Dec (Independence Day) not charged.
    assert (created["vacation_days"], created["weekend_days"], created["holiday_days"]) == (
        6,
        2,
        1,
    )
    detail = client.get(f"/api/v1/requests/{created['id']}", headers=employee_headers).json()
    assert [d["kind"] for d in detail["leave_days"]] == [
        "workday",
        "workday",
        "holiday",
        "workday",
        "workday",
        "weekend",
        "weekend",
    ]


def test_profile_update_applies_only_after_manager_approval(
    client, employee_headers, manager_headers
):
    before = me(client, employee_headers)
    created = client.post(
        "/api/v1/requests",
        headers=employee_headers,
        json={
            "type": "Profile update",
            "profile_changes": {"phone": "+7 701 555 12 34", "emergency_contact": "Mother"},
            "reason": "New number",
        },
    )
    assert created.status_code == 201, created.text
    req = created.json()
    assert req["status"] == "Pending" and req["vacation_days"] is None
    assert req["profile_changes"] == {
        "phone": {"from": None, "to": "+7 701 555 12 34"},
        "emergency_contact": {"from": None, "to": "Mother"},
    }
    pending = me(client, employee_headers)
    assert pending["phone"] is None and pending["pending_profile_change"] == req["profile_changes"]
    again = client.post(
        "/api/v1/requests",
        headers=employee_headers,
        json={"type": "Profile update", "profile_changes": {"location": "Astana, Kazakhstan"}},
    )
    assert again.status_code == 409

    queue = client.get("/api/v1/manager/requests?status=Pending", headers=manager_headers).json()
    assert req["id"] in [r["id"] for r in queue]
    approved = client.post(
        f"/api/v1/requests/{req['id']}/approve", headers=manager_headers, json={}
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["external_sync_id"] is None
    after = me(client, employee_headers)
    assert (after["phone"], after["emergency_contact"]) == ("+7 701 555 12 34", "Mother")
    assert after["pending_profile_change"] is None
    assert after["leave_balance_days"] == before["leave_balance_days"]


def test_rejected_profile_update_changes_nothing(client, employee_headers, manager_headers):
    req = client.post(
        "/api/v1/requests",
        headers=employee_headers,
        json={"type": "Profile update", "profile_changes": {"location": "Astana, Kazakhstan"}},
    ).json()
    client.post(f"/api/v1/requests/{req['id']}/reject", headers=manager_headers, json={})
    assert me(client, employee_headers)["location"] != "Astana, Kazakhstan"


def test_profile_update_accepts_only_real_contact_changes(client, employee_headers):
    current = client.get(
        "/api/v1/me/profile", headers={**employee_headers, "Accept-Language": "en"}
    ).json()
    invalid = [
        {"type": "Profile update", "profile_changes": {"department": "Finance"}},
        {"type": "Profile update", "profile_changes": {"phone": "call me"}},
        {"type": "Profile update", "profile_changes": {}},
        {
            "type": "Profile update",
            "start_date": "2026-12-01",
            "profile_changes": {"phone": "+77015550000"},
        },
        {"type": "Vacation", "start_date": "2026-12-01", "profile_changes": {"phone": "+7701"}},
        {"type": "Profile update", "profile_changes": {"location": current["location"]}},
    ]
    for body in invalid:
        res = client.post("/api/v1/requests", headers=employee_headers, json=body)
        assert res.status_code == 422, (body, res.text)


def test_hr_sees_account_details_that_a_manager_does_not(
    client, employee_headers, manager_headers, hr_admin_headers
):
    employee_id = me(client, employee_headers)["user_id"]
    hr = client.get(f"/api/v1/manager/team/{employee_id}", headers=hr_admin_headers).json()
    assert hr["email"] == "aruzhan@janapost.kz" and hr["role"] == "employee"
    assert hr["is_active"] is True and hr["account_created_at"]
    assert hr["last_sign_in_at"]  # the employee fixture signed in
    manager = client.get(f"/api/v1/manager/team/{employee_id}", headers=manager_headers).json()
    assert manager["email"] is None and manager["last_sign_in_at"] is None
    assert manager["emergency_contact"] is None and "phone" in manager
