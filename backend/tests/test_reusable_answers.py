from __future__ import annotations

from fastapi.testclient import TestClient


def _register(client: TestClient) -> dict:
    response = client.post(
        "/api/auth/register",
        json={"email": "reusableanswers@example.com", "password": "testpassword123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_reusable_answer(client: TestClient):
    headers = _register(client)

    response = client.post(
        "/api/reusable-answers",
        json={
            "canonical_question": "Are you authorized to work in the US?",
            "semantic_variants": ["Are you legally authorized to work in the United States?"],
            "exact_answer": "Yes",
            "risk_level": "high",
            "categories": ["work_authorization"],
        },
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["exact_answer"] == "Yes"
    assert data["user_approved"] is True

    response = client.get("/api/reusable-answers", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_update_reusable_answer(client: TestClient):
    headers = _register(client)
    created = client.post(
        "/api/reusable-answers",
        json={"canonical_question": "What is your gender?", "exact_answer": "Male", "risk_level": "high"},
        headers=headers,
    ).json()

    response = client.patch(
        f"/api/reusable-answers/{created['id']}",
        json={"exact_answer": "Prefer not to say"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["exact_answer"] == "Prefer not to say"


def test_delete_reusable_answer(client: TestClient):
    headers = _register(client)
    created = client.post(
        "/api/reusable-answers",
        json={"canonical_question": "Are you a veteran?", "exact_answer": "No", "risk_level": "high"},
        headers=headers,
    ).json()

    response = client.delete(f"/api/reusable-answers/{created['id']}", headers=headers)
    assert response.status_code == 204

    response = client.get("/api/reusable-answers", headers=headers)
    assert response.json() == []


def test_reusable_answers_are_scoped_per_user(client: TestClient):
    headers_a = _register(client)
    client.post(
        "/api/reusable-answers",
        json={"canonical_question": "Do you have a disability?", "exact_answer": "No", "risk_level": "high"},
        headers=headers_a,
    )

    response = client.post(
        "/api/auth/register",
        json={"email": "otheruser@example.com", "password": "testpassword123"},
    )
    headers_b = {"Authorization": f"Bearer {response.json()['access_token']}"}

    response = client.get("/api/reusable-answers", headers=headers_b)
    assert response.json() == []
