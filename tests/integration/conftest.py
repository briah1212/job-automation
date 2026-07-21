"""Shared fixtures for the browser-worker state machine integration suite.

Runs from the HOST (or a CI runner) against the dockerized stack's published
ports - postgres:5432, api:8001, mock-ats:8080 - the same way a real CI job
would: `docker compose up -d` first, then `pytest tests/integration`. This is
deliberately outside apps/browser-worker/tests (which runs *inside* the
browser-worker container and can't itself drive `docker compose restart` for
the container-recovery test).
"""
import itertools
import os
import subprocess
import time
import uuid

import psycopg2
import pytest
import requests

API_URL = os.environ.get("TEST_API_URL", "http://localhost:8001")
MOCK_ATS_URL = os.environ.get("TEST_MOCK_ATS_URL", "http://mock-ats:8080")  # from inside the docker network
DB_DSN = os.environ.get(
    "TEST_DATABASE_DSN",
    "host=localhost port=5432 dbname=job_automation user=postgres password=postgres",
)
POLL_TIMEOUT_SECONDS = int(os.environ.get("TEST_POLL_TIMEOUT_SECONDS", "60"))

_email_counter = itertools.count()


def unique_email(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}-{next(_email_counter)}@example.com"


@pytest.fixture(scope="session", autouse=True)
def _require_stack_reachable():
    """Fail fast with a clear message if the stack isn't up, rather than
    every individual test timing out confusingly."""
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        response.raise_for_status()
    except Exception as exc:
        pytest.skip(f"api not reachable at {API_URL} - run `docker compose up -d` first ({exc})")


@pytest.fixture
def db_conn():
    conn = psycopg2.connect(DB_DSN)
    conn.autocommit = True
    try:
        yield conn
    finally:
        conn.close()


class ApiClient:
    """Thin wrapper matching how the frontend/API consumer actually calls this API."""

    def __init__(self, token: str):
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}"}

    def post(self, path: str, **kwargs):
        return requests.post(f"{API_URL}{path}", headers=self.headers, timeout=30, **kwargs)

    def put(self, path: str, **kwargs):
        return requests.put(f"{API_URL}{path}", headers=self.headers, timeout=30, **kwargs)

    def get(self, path: str, **kwargs):
        return requests.get(f"{API_URL}{path}", headers=self.headers, timeout=30, **kwargs)


@pytest.fixture
def user(db_conn):
    """Register a fresh user + minimal profile, matching what BrowserWorker
    requires (legal_name, email, work_authorization) - see
    queue_worker._build_application_data."""
    email = unique_email("inttest")
    response = requests.post(
        f"{API_URL}/api/auth/register", json={"email": email, "password": "testpass123"}, timeout=10
    )
    response.raise_for_status()
    token = response.json()["access_token"]
    client = ApiClient(token)

    profile_response = client.put(
        "/api/profile",
        json={"legal_name": "Integration Test", "email": email, "work_authorization": "yes"},
    )
    assert profile_response.status_code == 200, profile_response.text

    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        user_id = cur.fetchone()[0]

    yield {"email": email, "token": token, "client": client, "user_id": str(user_id)}

    # Cleanup - cascades applications/jobs/browser_sessions/ats_credentials;
    # workflow_tasks has no FK to users so needs an explicit delete.
    with db_conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM workflow_tasks WHERE entity_id IN (
                SELECT id FROM applications WHERE user_id = %s
            )
            """,
            (user_id,),
        )
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))


@pytest.fixture
def resume_attached_application(user, db_conn):
    """Create a job + application with a real (fixture) resume already
    attached, so runs can reach past RESUME_UPLOAD without needing a
    separate manual-intervention step first."""
    client = user["client"]

    job_response = client.post("/api/jobs/import-url", json={"url": MOCK_ATS_URL})
    assert job_response.status_code < 300, job_response.text
    job_id = job_response.json()["id"]

    app_response = client.post("/api/applications", json={"job_id": job_id})
    assert app_response.status_code < 300, app_response.text
    application_id = app_response.json()["id"]

    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO resume_families (id, user_id, name, status, created_at, updated_at)
            VALUES (gen_random_uuid(), %s, 'Integration Family', 'ready', now(), now())
            RETURNING id
            """,
            (user["user_id"],),
        )
        family_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO resume_versions (id, family_id, version, status, file_path, parsed_data, created_at, updated_at)
            VALUES (gen_random_uuid(), %s, 1, 'ready', 'resumes/integration-test/resume.pdf', '{}', now(), now())
            RETURNING id
            """,
            (family_id,),
        )
        resume_version_id = cur.fetchone()[0]
        cur.execute(
            "UPDATE applications SET resume_version_id = %s WHERE id = %s",
            (resume_version_id, application_id),
        )

    return {"application_id": application_id, "job_id": job_id, **user}


def ensure_fixture_resume_file():
    """The fixture resume file referenced by resume_attached_application must
    actually exist on the shared storage volume, mounted at ../../storage
    relative to this file (repo_root/storage) from the host."""
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(repo_root, "storage", "resumes", "integration-test", "resume.pdf")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(b"%PDF-1.4\n%%EOF")
    return path


def poll_until(predicate, timeout=POLL_TIMEOUT_SECONDS, interval=1.5, description="condition"):
    """Poll `predicate` (a zero-arg callable returning the value to check
    truthiness of, or raising) until it returns truthy or timeout expires."""
    deadline = time.monotonic() + timeout
    last_result = None
    while time.monotonic() < deadline:
        last_result = predicate()
        if last_result:
            return last_result
        time.sleep(interval)
    raise TimeoutError(f"Timed out after {timeout}s waiting for: {description} (last result: {last_result!r})")


def get_browser_status(client: ApiClient, application_id: str) -> dict:
    response = client.get(f"/api/applications/{application_id}/browser-status")
    response.raise_for_status()
    return response.json()


def wait_for_workflow_status(client: ApiClient, application_id: str, target_statuses, description: str) -> dict:
    """Poll until browser-status's top-level `status` (pending/running/
    waiting_user_input/completed/failed) is one of `target_statuses` - unlike
    polling on "the API call succeeded", which is always true and would
    return on the very first check regardless of whether the task has
    actually progressed."""
    if isinstance(target_statuses, str):
        target_statuses = (target_statuses,)

    def _check():
        current = get_browser_status(client, application_id)
        return current if current.get("status") in target_statuses else None

    return poll_until(_check, description=description)


def restart_browser_worker_container():
    """Shells out to docker compose - only viable from the host/CI runner,
    which is exactly why this test suite lives outside the browser-worker
    container's own pytest run."""
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    subprocess.run(
        ["docker", "compose", "restart", "browser-worker"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        timeout=60,
    )
