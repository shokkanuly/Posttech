def test_list_requests_employee(client, employee_headers):
    res = client.get("/api/v1/requests", headers=employee_headers)
    assert res.status_code == 200
    requests = res.json()
    assert len(requests) >= 3
    # Check all belong to Aruzhan
    for r in requests:
        assert r["user_name"] == "Aruzhan Sadykova"


def test_create_vacation_request_success(client, employee_headers):
    payload = {
        "type": "Vacation",
        "start_date": "2026-11-02",
        "end_date": "2026-11-04",
        "reason": "Autumn rest days",
    }
    res = client.post("/api/v1/requests", json=payload, headers=employee_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["type"] == "Vacation"
    assert data["status"] == "Pending"
    assert data["request_code"].startswith("REQ-")
    assert "02 Nov 2026 – 04 Nov 2026" in data["period_or_details"]


def test_create_vacation_request_invalid_dates(client, employee_headers):
    # End date before start date
    payload = {
        "type": "Vacation",
        "start_date": "2026-11-05",
        "end_date": "2026-11-02",
        "reason": "Invalid dates",
    }
    res = client.post("/api/v1/requests", json=payload, headers=employee_headers)
    assert res.status_code == 422


def test_create_vacation_request_excessive_balance(client, employee_headers):
    # Requesting 100 days when balance is ~18.5
    payload = {
        "type": "Vacation",
        "start_date": "2026-11-01",
        "end_date": "2027-02-15",
        "reason": "Excessive leave",
    }
    res = client.post("/api/v1/requests", json=payload, headers=employee_headers)
    assert res.status_code == 400
    assert "Insufficient leave balance" in res.json()["detail"]


def test_create_advance_payment_request(client, employee_headers):
    payload = {
        "type": "Advance payment",
        "start_date": "2026-11-10",
        "amount": 75000.0,
        "reason": "Home repair expenses",
    }
    res = client.post("/api/v1/requests", json=payload, headers=employee_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["type"] == "Advance payment"
    assert data["amount"] == 75000.0


def test_manager_review_direct_report_approval(client, manager_headers, employee_headers):
    # 1. Employee creates a request
    payload = {
        "type": "Vacation",
        "start_date": "2026-12-01",
        "end_date": "2026-12-02",
        "reason": "Winter holiday",
    }
    create_res = client.post("/api/v1/requests", json=payload, headers=employee_headers)
    assert create_res.status_code == 201
    req_id = create_res.json()["id"]

    # 2. Manager approves it
    review_payload = {"action": "approve", "comment": "Approved by manager Timur"}
    res = client.post(
        f"/api/v1/requests/{req_id}/approve", json=review_payload, headers=manager_headers
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "Approved"
    assert data["reviewer_name"] == "Timur Kasymov"
    assert data["external_sync_id"] is None  # Documentolog is unconnected.

    # Verify event history exists
    assert len(data["events"]) >= 2
    event_types = [e["event_type"] for e in data["events"]]
    assert "SUBMITTED" in event_types
    assert "APPROVED" in event_types


def test_employee_cannot_approve_own_request(client, employee_headers):
    payload = {
        "type": "Vacation",
        "start_date": "2026-12-10",
        "end_date": "2026-12-11",
        "reason": "Test approval",
    }
    create_res = client.post("/api/v1/requests", json=payload, headers=employee_headers)
    assert create_res.status_code == 201
    req_id = create_res.json()["id"]

    # Employee attempts to self-approve
    res = client.post(
        f"/api/v1/requests/{req_id}/approve", json={"action": "approve"}, headers=employee_headers
    )
    assert res.status_code == 403
    assert "Employees cannot approve or reject requests" in res.json()["detail"]


def test_advance_amount_preserves_fractional_display(client, employee_headers):
    result = client.post(
        "/api/v1/requests",
        headers=employee_headers,
        json={"type": "Advance payment", "start_date": "2026-11-10", "amount": 150000.25},
    )
    assert result.status_code == 201
    assert result.json()["amount"] == 150000.25
    assert "150,000.25 ₸" in result.json()["period_or_details"]
