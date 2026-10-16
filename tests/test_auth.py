def test_login_successful(client):
    res = client.post(
        "/api/v1/auth/login", json={"email": "aruzhan@janapost.kz", "password": "Password123!"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "aruzhan@janapost.kz"
    assert data["user"]["role"] == "employee"


def test_login_invalid_password(client):
    res = client.post(
        "/api/v1/auth/login", json={"email": "aruzhan@janapost.kz", "password": "WrongPassword"}
    )
    assert res.status_code == 401
    assert "Incorrect email or password" in res.json()["detail"]


def test_login_nonexistent_user(client):
    res = client.post(
        "/api/v1/auth/login", json={"email": "unknown@janapost.kz", "password": "Password123!"}
    )
    assert res.status_code == 401


def test_get_me_unauthenticated(client):
    res = client.get("/api/v1/me")
    assert res.status_code == 401


def test_get_me_authenticated(client, employee_headers):
    res = client.get("/api/v1/me", headers=employee_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["user"]["full_name"] == "Aruzhan Sadykova"
    assert data["profile"]["employee_code"] == "JP-10428"
    assert data["profile"]["company"] == "Jana Post Kazakhstan"


def test_get_my_profile(client, employee_headers):
    res = client.get("/api/v1/me/profile", headers=employee_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["employee_code"] == "JP-10428"
    assert data["manager_name"] == "Timur Kasymov"
    assert data["is_official_hr_data"] is False  # No external 1C verification.
    assert data["read_only"] is True


def test_get_my_dashboard(client, employee_headers):
    res = client.get("/api/v1/me/dashboard", headers=employee_headers)
    assert res.status_code == 200
    data = res.json()
    assert "Aruzhan" in data["greeting"]
    assert data["leave_balance_days"] > 0
    assert "open_requests_count" in data
    assert "learning_progress_percent" in data
