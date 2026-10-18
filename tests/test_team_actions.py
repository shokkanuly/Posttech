"""Notification links, manager/HR actions on an employee, and lesson order."""

from tests.conftest import login


def team_member_id(client, manager_headers):
    return client.get("/api/v1/manager/team", headers=manager_headers).json()[0]["user_id"]


def test_notifications_link_to_the_request_for_requester_and_reviewer(
    client, employee_headers, manager_headers
):
    created = client.post(
        "/api/v1/requests",
        headers=employee_headers,
        json={"type": "Advance payment", "start_date": "2027-01-11", "amount": 50000},
    ).json()
    for headers in (employee_headers, manager_headers):
        notice = next(
            n
            for n in client.get("/api/v1/notifications", headers=headers).json()
            if n["reference_id"] == created["request_code"]
        )
        assert notice["reference_record_id"] == created["id"]
        opened = client.patch(
            f"/api/v1/notifications/{notice['id']}", headers=headers, json={"is_read": True}
        ).json()
        assert opened["is_read"] and opened["reference_record_id"] == created["id"]
        assert client.get(f"/api/v1/requests/{created['id']}", headers=headers).status_code == 200


def test_manager_assigns_a_course_to_a_report_only(
    client, employee_headers, manager_headers, hr_admin_headers
):
    # Dana reports to Timur and has no seeded courses.
    dana_headers = {"Authorization": "Bearer " + login(client, "dana@janapost.kz")}
    employee = client.get("/api/v1/me", headers=dana_headers).json()["user"]["id"]
    course = client.post(
        f"/api/v1/manager/team/{employee}/courses", headers=manager_headers, json={"course_id": 2}
    )
    assert course.status_code == 200, course.text
    mine = client.get("/api/v1/courses/2", headers=dana_headers).json()
    assert mine["assigned"] is True
    notice = next(
        n
        for n in client.get("/api/v1/notifications", headers=dana_headers).json()
        if n["reference_type"] == "course" and n["reference_id"] == mine["code"]
    )
    assert notice["reference_record_id"] == 2
    hr_id = client.get("/api/v1/me", headers=hr_admin_headers).json()["user"]["id"]
    outside = client.post(
        f"/api/v1/manager/team/{hr_id}/courses", headers=manager_headers, json={"course_id": 2}
    )
    assert outside.status_code == 404
    denied = client.post(
        f"/api/v1/manager/team/{employee}/courses", headers=employee_headers, json={"course_id": 2}
    )
    assert denied.status_code == 403


def test_request_filed_for_an_employee_is_approved_by_the_filer(
    client, employee_headers, manager_headers
):
    employee = team_member_id(client, manager_headers)
    balance = client.get("/api/v1/me/profile", headers=employee_headers).json()[
        "leave_balance_days"
    ]
    filed = client.post(
        f"/api/v1/manager/team/{employee}/requests",
        headers=manager_headers,
        json={"type": "Vacation", "start_date": "2027-01-11", "end_date": "2027-01-12"},
    )
    assert filed.status_code == 201, filed.text
    req = filed.json()
    manager_name = client.get("/api/v1/me", headers=manager_headers).json()["user"]["full_name"]
    assert req["status"] == "Approved" and req["user_id"] == employee
    assert sorted((e["event_type"], e["actor_name"]) for e in req["events"]) == [
        ("APPROVED", manager_name),
        ("SUBMITTED", manager_name),
    ]
    profile = client.get("/api/v1/me/profile", headers=employee_headers).json()
    assert profile["leave_balance_days"] == balance - 2
    titles = [
        n["title"]
        for n in client.get("/api/v1/notifications", headers=employee_headers).json()
        if n["reference_id"] == req["request_code"]
    ]
    assert titles == ["Request Approved"]
    assert not any(
        n["reference_id"] == req["request_code"]
        for n in client.get("/api/v1/notifications", headers=manager_headers).json()
    )


def test_filing_for_yourself_or_contact_changes_is_refused(client, manager_headers):
    me = client.get("/api/v1/me", headers=manager_headers).json()["user"]["id"]
    own = client.post(
        f"/api/v1/manager/team/{me}/requests",
        headers=manager_headers,
        json={"type": "Advance payment", "start_date": "2027-01-11", "amount": 50000},
    )
    assert own.status_code == 422
    contact = client.post(
        f"/api/v1/manager/team/{team_member_id(client, manager_headers)}/requests",
        headers=manager_headers,
        json={"type": "Profile update", "profile_changes": {"phone": "+7 700 111 22 33"}},
    )
    assert contact.status_code == 422


def test_lesson_quizzes_open_in_order(client, manager_headers, hr_admin_headers):
    manager_id = client.get("/api/v1/me", headers=manager_headers).json()["user"]["id"]
    client.post(
        "/api/v1/admin/enrollments",
        headers=hr_admin_headers,
        json={"user_id": manager_id, "course_id": 1},
    )
    lessons = client.get("/api/v1/courses/1", headers=manager_headers).json()["lessons"]
    quiz = "/api/v1/courses/lessons/{}/quiz"
    skipped = client.post(
        quiz.format(lessons[1]["id"]), headers=manager_headers, json={"answer_index": 0}
    )
    assert skipped.status_code == 409
    first = client.post(
        quiz.format(lessons[0]["id"]), headers=manager_headers, json={"answer_index": 1}
    )
    assert first.json()["passed"] is True
    second = client.post(
        quiz.format(lessons[1]["id"]), headers=manager_headers, json={"answer_index": 0}
    )
    assert second.status_code == 200
