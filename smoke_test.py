#!/usr/bin/env python3
"""
JanaMen Digital HR — Live Demonstration Smoke Test Runner
Runs the full 10-step hackathon judging scenario against the running server (http://127.0.0.1:8000).
"""

import json
import os
import urllib.error
import urllib.request

BASE_URL = os.getenv("JANAMEN_BASE_URL", "http://127.0.0.1:8000")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "Password123!")


def log_step(num, title):
    print(f"\n{'=' * 70}\n[STEP {num}] {title}\n{'=' * 70}")


def request(path, method="GET", data=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        try:
            return e.code, json.loads(err_body)
        except Exception:
            return e.code, {"error": err_body}


def main():
    print("🚀 Starting JanaMen Digital HR Live Smoke Test...")

    # Step 1: Employee login and dashboard
    log_step(1, "Employee Login & Personalized Dashboard")
    status, res = request(
        "/api/v1/auth/login",
        method="POST",
        data={"email": "aruzhan@janapost.kz", "password": DEMO_PASSWORD},
    )
    assert status == 200, f"Login failed: {res}"
    emp_token = res["access_token"]
    emp_user = res["user"]
    print(f"✓ Authenticated: {emp_user['full_name']} (Role: {emp_user['role']})")

    status, dash = request("/api/v1/me/dashboard", token=emp_token)
    assert status == 200
    print(
        f"✓ Dashboard loaded: Greeting = '{dash['greeting']}', Leave balance = {dash['leave_balance_days']} days, Learning = {dash['learning_progress_percent']}%"
    )

    # Step 2: Profile & Leave balance (Read-Only)
    log_step(2, "Employee Profile & Read-Only Local HR Data")
    status, prof = request("/api/v1/me/profile", token=emp_token)
    assert status == 200
    print(
        f"✓ Profile loaded: Code = {prof['employee_code']}, Dept = {prof['department']}, Manager = {prof['manager_name']}"
    )
    assert prof["read_only"] is True and prof["is_official_hr_data"] is False
    print("✓ Official HR data flags: read_only=True; local synthetic data, 1C unconnected")

    # Step 3: Request submission (Vacation)
    log_step(3, "Request Submission & Event Audit History")
    vac_payload = {
        "type": "Vacation",
        "start_date": "2026-11-23",
        "end_date": "2026-11-25",
        "reason": "Family gathering & trip",
    }
    status, new_req = request("/api/v1/requests", method="POST", data=vac_payload, token=emp_token)
    assert status == 201, f"Failed: {new_req}"
    req_id = new_req["id"]
    req_code = new_req["request_code"]
    print(f"✓ Request created: {req_code} ({new_req['type']}) -> Status: {new_req['status']}")

    # Step 4: Manager review & approval
    log_step(4, "Manager Portal: Team Approval Queue & Review Action")
    status, mgr_res = request(
        "/api/v1/auth/login",
        method="POST",
        data={"email": "timur@janapost.kz", "password": DEMO_PASSWORD},
    )
    assert status == 200
    mgr_token = mgr_res["access_token"]
    print(f"✓ Authenticated Manager: {mgr_res['user']['full_name']}")

    status, team_reqs = request("/api/v1/manager/requests?status=Pending", token=mgr_token)
    assert status == 200
    assert any(r["id"] == req_id for r in team_reqs)
    print(f"✓ Manager sees {len(team_reqs)} pending request(s) for direct reports.")

    status, approved_req = request(
        f"/api/v1/requests/{req_id}/approve",
        method="POST",
        data={"action": "approve", "comment": "Approved by manager Timur. Coverage arranged."},
        token=mgr_token,
    )
    assert status == 200
    print(f"✓ Request {req_code} approved. Reviewer: {approved_req['reviewer_name']}")
    print(
        f"✓ Documentolog local reference (unconnected by default): {approved_req['external_sync_id']}"
    )

    # Step 5: Employee notifications & updated balance
    log_step(5, "Employee Notifications & Updated Local Leave Balance")
    status, notifs = request("/api/v1/notifications", token=emp_token)
    assert status == 200
    approved_notif = next(
        (n for n in notifs if req_code in n["message"] and "Approved" in n["title"]), None
    )
    assert approved_notif is not None
    print(
        f"✓ Notification received by employee: '{approved_notif['title']}' - {approved_notif['message']}"
    )

    status, updated_prof = request("/api/v1/me/profile", token=emp_token)
    assert status == 200 and updated_prof["leave_balance_days"] == prof["leave_balance_days"] - 3

    # Step 6: Jana Academy Course & Interactive Quiz
    log_step(6, "Jana Academy: Course Progression & Persisted Completion")
    status, courses = request("/api/v1/courses", token=emp_token)
    c1 = next(c for c in courses if c["code"] == "CRS-SEC-101")
    print(f"✓ Course '{c1['title']}' initial progress: {c1['progress_percent']}%")

    status, c_detail = request(f"/api/v1/courses/{c1['id']}", token=emp_token)
    lesson4 = c_detail["lessons"][3]

    status, quiz_res = request(
        f"/api/v1/courses/lessons/{lesson4['id']}/quiz",
        method="POST",
        data={"answer_index": 0},
        token=emp_token,
    )
    assert status == 200 and quiz_res["passed"] is True
    print(f"✓ Quiz submitted successfully: {quiz_res['explanation']}")
    print(
        f"✓ New course progress: {quiz_res['new_progress_percent']}% (Course completed: {quiz_res['course_completed']})"
    )

    # Step 7: AI Jana Grounded Q&A with Citation
    log_step(7, "AI Jana: Knowledge-Grounded Q&A with Source Citation")
    status, ai_res = request(
        "/api/v1/ai/chat",
        method="POST",
        data={"question": "How do I request vacation?"},
        token=emp_token,
    )
    assert status == 200 and ai_res["answer_status"] == "grounded"
    print(f"✓ AI Jana grounded status: '{ai_res['answer_status']}'")
    print(
        f"✓ Cited source: {ai_res['sources'][0]['document_title']} · {ai_res['sources'][0]['section_title']}"
    )
    print(f"✓ Response snippet: {ai_res['answer'][:150]}...")

    # Step 8: AI Jana Safe Fallback (No Hallucinations)
    log_step(8, "AI Jana: Safe Fallback for Unsupported Inquiries")
    status, ai_fall = request(
        "/api/v1/ai/chat",
        method="POST",
        data={"question": "What is the pet insurance reimbursement policy?"},
        token=emp_token,
    )
    assert status == 200 and ai_fall["answer_status"] == "fallback"
    print(f"✓ Fallback behavior verified: Status = '{ai_fall['answer_status']}'")
    print(f"✓ Escalation guidance provided: '{ai_fall['escalation_guidance']}'")

    # Step 9: Unauthorized Data Access Denied (RBAC / IDOR Protection)
    log_step(9, "Security Verification: Server-Enforced RBAC Denials")
    status, denied_mgr = request("/api/v1/manager/requests", token=emp_token)
    assert status == 403, f"Expected 403 Forbidden, got {status}"
    print(
        f"✓ Employee accessing Manager endpoint returned HTTP 403 Forbidden: {denied_mgr['detail']}"
    )

    status, denied_admin = request("/api/v1/admin/knowledge", token=emp_token)
    assert status == 403, f"Expected 403 Forbidden, got {status}"
    print(
        f"✓ Employee accessing HR Admin endpoint returned HTTP 403 Forbidden: {denied_admin['detail']}"
    )

    # Step 10: Unconnected Integration Boundaries (1C:ZUP & Documentolog)
    log_step(10, "HR Administration & Integration Boundaries Telemetry")
    status, admin_res = request(
        "/api/v1/auth/login",
        method="POST",
        data={"email": "aigerim@janapost.kz", "password": DEMO_PASSWORD},
    )
    admin_token = admin_res["access_token"]
    status, adapters = request("/api/v1/admin/integrations", token=admin_token)
    assert status == 200 and len(adapters) == 2
    for a in adapters:
        print(f"✓ Adapter '{a['adapter_name']}' -> Status: {a['status']}, Mode: {a['mode']}")

    status, logged_out = request("/api/v1/auth/logout", method="POST", token=emp_token)
    assert status == 200
    status, _ = request("/api/v1/me", token=emp_token)
    assert status == 401
    print("✓ Logout invalidates the employee session.")

    print("\n" + "*" * 70)
    print("🎉 ALL 10 API SMOKE STEPS PASSED (browser checks are separate)!")
    print("*" * 70 + "\n")


if __name__ == "__main__":
    main()
