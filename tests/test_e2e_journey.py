def test_full_hackathon_demo_journey(client):
    # Step 1: Employee login and dashboard
    login_res = client.post("/api/v1/auth/login", json={"email": "aruzhan@janapost.kz", "password": "Password123!"})
    assert login_res.status_code == 200
    emp_token = login_res.json()["access_token"]
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    dash_res = client.get("/api/v1/me/dashboard", headers=emp_headers)
    assert dash_res.status_code == 200
    assert dash_res.json()["user_name"] == "Aruzhan Sadykova"

    # Step 2: Profile & Leave balance
    prof_res = client.get("/api/v1/me/profile", headers=emp_headers)
    assert prof_res.status_code == 200
    prof = prof_res.json()
    assert prof["employee_code"] == "JP-10428"
    assert prof["department"] == "Product Operations"
    initial_balance = prof["leave_balance_days"]

    # Step 3: Request submission (2 days vacation)
    req_payload = {
        "type": "Vacation",
        "start_date": "2026-11-16",
        "end_date": "2026-11-17",
        "reason": "Hackathon Demo Time Off",
    }
    submit_res = client.post("/api/v1/requests", json=req_payload, headers=emp_headers)
    assert submit_res.status_code == 201
    req_data = submit_res.json()
    created_id = req_data["id"]
    assert req_data["status"] == "Pending"

    # Step 4: Manager login and review & approval
    mgr_login = client.post("/api/v1/auth/login", json={"email": "timur@janapost.kz", "password": "Password123!"})
    assert mgr_login.status_code == 200
    mgr_token = mgr_login.json()["access_token"]
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}

    team_reqs = client.get("/api/v1/manager/requests?status=Pending", headers=mgr_headers).json()
    assert any(r["id"] == created_id for r in team_reqs)

    appr_res = client.post(
        f"/api/v1/requests/{created_id}/approve",
        json={"action": "approve", "comment": "Approved for demo walkthrough"},
        headers=mgr_headers,
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "Approved"

    # Step 5: Employee notifications and updated request history
    notifs_res = client.get("/api/v1/notifications", headers=emp_headers)
    assert notifs_res.status_code == 200
    assert any("Approved" in n["title"] or "Approved" in n["message"] for n in notifs_res.json())

    # Verify updated leave balance reflects deduction (2 days)
    new_prof = client.get("/api/v1/me/profile", headers=emp_headers).json()
    assert new_prof["leave_balance_days"] == initial_balance - 2.0

    # Step 6: Course completion in Jana Academy
    courses = client.get("/api/v1/courses", headers=emp_headers).json()
    c_id = next(c["id"] for c in courses if c["code"] == "CRS-SEC-101")
    detail = client.get(f"/api/v1/courses/{c_id}", headers=emp_headers).json()
    l_id = detail["lessons"][3]["id"]

    quiz_res = client.post(
        f"/api/v1/courses/lessons/{l_id}/quiz",
        json={"answer_index": 0},
        headers=emp_headers,
    )
    assert quiz_res.status_code == 200
    assert quiz_res.json()["course_completed"] is True

    # Step 7: AI Jana answer with verifiable source
    ai_res = client.post("/api/v1/ai/chat", json={"question": "How do I request vacation?"}, headers=emp_headers)
    assert ai_res.status_code == 200
    assert ai_res.json()["answer_status"] == "grounded"
    assert len(ai_res.json()["sources"]) > 0

    # Step 8: AI Jana safe fallback for unsupported question
    ai_fall = client.post("/api/v1/ai/chat", json={"question": "What is the policy for airline frequent flyer miles?"}, headers=emp_headers)
    assert ai_fall.status_code == 200
    assert ai_fall.json()["answer_status"] == "fallback"
    assert len(ai_fall.json()["sources"]) == 0

    # Step 9: Unauthorized data-access attempt denied (Employee trying to view manager requests)
    denied_res = client.get("/api/v1/manager/requests", headers=emp_headers)
    assert denied_res.status_code == 403

    # Step 10: Enterprise integration boundaries telemetry
    admin_login = client.post("/api/v1/auth/login", json={"email": "aigerim@janapost.kz", "password": "Password123!"})
    assert admin_login.status_code == 200
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    integ_res = client.get("/api/v1/admin/integrations", headers=admin_headers)
    assert integ_res.status_code == 200
    assert len(integ_res.json()) == 2
