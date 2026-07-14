from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_root(client: TestClient):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Job Automation Platform API"}


def test_health(client: TestClient):
    """Test health check."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_register_user(client: TestClient):
    """Test user registration."""
    response = client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "testpassword123"}
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_register_duplicate_email(client: TestClient):
    """Test registration with duplicate email."""
    # Register first user
    client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "testpassword123"}
    )
    
    # Try to register again with same email
    response = client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "anotherpassword"}
    )
    assert response.status_code == 400


def test_login(client: TestClient):
    """Test user login."""
    # Register user
    client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "testpassword123"}
    )
    
    # Login
    response = client.post(
        "/api/auth/login",
        data={"username": "test@example.com", "password": "testpassword123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client: TestClient):
    """Test login with wrong password."""
    # Register user
    client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "testpassword123"}
    )
    
    # Try to login with wrong password
    response = client.post(
        "/api/auth/login",
        data={"username": "test@example.com", "password": "wrongpassword"}
    )
    assert response.status_code == 401


def test_profile_create_and_get(client: TestClient):
    """Test profile creation and retrieval."""
    # Register and login
    register_response = client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "testpassword123"}
    )
    token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Update profile
    profile_data = {
        "legal_name": "John Doe",
        "preferred_name": "John",
        "email": "john@example.com",
        "phone": "+1234567890",
        "career_interests": "Software Engineering"
    }
    response = client.put("/api/profile", json=profile_data, headers=headers)
    assert response.status_code == 200
    
    # Get profile
    response = client.get("/api/profile", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["legal_name"] == "John Doe"
    assert data["email"] == "john@example.com"


def test_profile_unauthorized(client: TestClient):
    """Test profile access without authentication."""
    response = client.get("/api/profile")
    assert response.status_code == 401


def test_list_jobs(client: TestClient):
    """Test listing jobs."""
    # Register and login
    register_response = client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "testpassword123"}
    )
    token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # List jobs (should be empty)
    response = client.get("/api/jobs", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


def test_import_job_from_url(client: TestClient):
    """Test importing a job from URL."""
    # Register and login
    register_response = client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "testpassword123"}
    )
    token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Import job
    response = client.post(
        "/api/jobs/import-url",
        json={"url": "https://example.com/job/123"},
        headers=headers
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["status"] == "extracting"
