def test_list_courses(client, employee_headers):
    res = client.get("/api/v1/courses", headers=employee_headers)
    assert res.status_code == 200
    courses = res.json()
    assert len(courses) >= 2
    # Verify Data protection essentials exists
    sec_course = next((c for c in courses if c["code"] == "CRS-SEC-101"), None)
    assert sec_course is not None
    assert sec_course["is_mandatory"] is True
    # Initial seeded progress is 75.0%
    assert sec_course["progress_percent"] == 75.0


def test_get_course_detail(client, employee_headers):
    # Fetch first course
    list_res = client.get("/api/v1/courses", headers=employee_headers)
    c_id = list_res.json()[0]["id"]

    res = client.get(f"/api/v1/courses/{c_id}", headers=employee_headers)
    assert res.status_code == 200
    detail = res.json()
    assert len(detail["lessons"]) == 4
    # Lessons 1, 2, 3 should be completed, 4 incomplete
    assert detail["lessons"][0]["is_completed"] is True
    assert detail["lessons"][1]["is_completed"] is True
    assert detail["lessons"][2]["is_completed"] is True
    assert detail["lessons"][3]["is_completed"] is False
    assert detail["current_lesson_id"] == detail["lessons"][3]["id"]


def test_complete_lesson_quiz_and_finish_course(client, employee_headers):
    # Fetch course detail to find lesson 4
    courses = client.get("/api/v1/courses", headers=employee_headers).json()
    c_id = next(c["id"] for c in courses if c["code"] == "CRS-SEC-101")
    detail = client.get(f"/api/v1/courses/{c_id}", headers=employee_headers).json()
    lesson_4 = detail["lessons"][3]

    # Lesson 4: Correct answer index is 0 ("Within 30 minutes")
    quiz_res = client.post(
        f"/api/v1/courses/lessons/{lesson_4['id']}/quiz",
        json={"answer_index": 0},
        headers=employee_headers,
    )
    assert quiz_res.status_code == 200
    data = quiz_res.json()
    assert data["passed"] is True
    assert data["new_progress_percent"] == 100.0
    assert data["course_completed"] is True

    # Verify course status updated to completed
    updated_course = client.get(f"/api/v1/courses/{c_id}", headers=employee_headers).json()
    assert updated_course["status"] == "COMPLETED"
    assert updated_course["progress_percent"] == 100.0
