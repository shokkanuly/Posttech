"""Leave calendar marking, the read-only profile and HR-only employee details."""

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


def test_profile_is_read_only_while_documentolog_is_unconnected(
    client, employee_headers, manager_headers
):
    before = me(client, employee_headers)
    created = client.post(
        "/api/v1/requests",
        headers={**employee_headers, "Accept-Language": "en"},
        json={"type": "Profile update", "profile_changes": {"phone": "+7 701 555 12 34"}},
    )
    assert created.status_code == 409, created.text
    assert "Documentolog" in created.json()["error"]["message"]
    after = me(client, employee_headers)
    assert after["phone"] == before["phone"] and after["pending_profile_change"] is None


def test_profile_update_accepts_only_real_contact_changes(client, employee_headers):
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
