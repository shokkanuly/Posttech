def test_employee_cannot_access_manager_portal(client, employee_headers):
    res = client.get("/api/v1/manager/requests", headers=employee_headers)
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]


def test_employee_cannot_access_admin_knowledge(client, employee_headers):
    res = client.get("/api/v1/admin/knowledge", headers=employee_headers)
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]


def test_manager_cannot_access_admin_portal(client, manager_headers):
    res = client.get("/api/v1/admin/knowledge", headers=manager_headers)
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]


def test_hr_admin_can_access_admin_portal(client, hr_admin_headers):
    res = client.get("/api/v1/admin/knowledge", headers=hr_admin_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_admin_integrations_telemetry(client, hr_admin_headers):
    res = client.get("/api/v1/admin/integrations", headers=hr_admin_headers)
    assert res.status_code == 200
    adapters = res.json()
    assert len(adapters) == 2
    adapter_names = [a["adapter_name"] for a in adapters]
    assert any("1C:Enterprise" in name for name in adapter_names)
    assert any("Documentolog" in name for name in adapter_names)


def test_invalid_bearer_token(client):
    headers = {"Authorization": "Bearer invalid.fake.token"}
    res = client.get("/api/v1/me", headers=headers)
    assert res.status_code == 401
