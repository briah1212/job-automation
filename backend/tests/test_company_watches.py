from __future__ import annotations

from fastapi.testclient import TestClient


def _register(client: TestClient) -> dict:
    response = client.post(
        "/api/auth/register",
        json={"email": "companywatches@example.com", "password": "testpassword123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_company_watch(client: TestClient):
    headers = _register(client)

    response = client.post(
        "/api/company-watches",
        json={"company_name": "Airtable", "ats_platform": "greenhouse", "board_identifier": "airtable"},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["company_name"] == "Airtable"
    assert data["enabled"] is True
    assert data["last_polled_at"] is None

    response = client.get("/api/company-watches", headers=headers)
    assert len(response.json()) == 1


def test_create_company_watch_rejects_unsupported_platform(client: TestClient):
    headers = _register(client)

    response = client.post(
        "/api/company-watches",
        json={"company_name": "Some Corp", "ats_platform": "workday", "board_identifier": "somecorp"},
        headers=headers,
    )
    assert response.status_code == 400


def test_disable_company_watch(client: TestClient):
    headers = _register(client)
    created = client.post(
        "/api/company-watches",
        json={"company_name": "Palantir", "ats_platform": "lever", "board_identifier": "palantir"},
        headers=headers,
    ).json()

    response = client.patch(
        f"/api/company-watches/{created['id']}",
        json={"enabled": False},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is False


def test_delete_company_watch(client: TestClient):
    headers = _register(client)
    created = client.post(
        "/api/company-watches",
        json={"company_name": "Confido", "ats_platform": "ashby", "board_identifier": "confido"},
        headers=headers,
    ).json()

    response = client.delete(f"/api/company-watches/{created['id']}", headers=headers)
    assert response.status_code == 204

    response = client.get("/api/company-watches", headers=headers)
    assert response.json() == []
