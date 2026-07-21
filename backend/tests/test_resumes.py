"""Regression test for the resume upload endpoint actually persisting bytes.

Found during real-ATS validation setup: upload_resume recorded a file_path in
the DB but never wrote the uploaded content anywhere (a TODO stub), so
BrowserWorker's later `os.path.join(_STORAGE_ROOT, resume_version.file_path)`
read would silently hit a missing file on any real application run.
"""
from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.api.routes.resumes import _STORAGE_ROOT, _safe_filename


def _register(client: TestClient) -> dict:
    response = client.post(
        "/api/auth/register",
        json={"email": "resumeupload@example.com", "password": "testpassword123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_upload_resume_writes_file_to_storage_root(client: TestClient):
    headers = _register(client)
    content = b"%PDF-1.4\nSome resume content\n%%EOF"

    response = client.post(
        "/api/resumes",
        files={"file": ("resume.pdf", content, "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    file_path = data["version"]["file_path"]

    absolute_path = os.path.join(_STORAGE_ROOT, file_path)
    assert os.path.isfile(absolute_path)
    with open(absolute_path, "rb") as f:
        assert f.read() == content

    os.remove(absolute_path)


def test_upload_resume_sanitizes_path_traversal_filename(client: TestClient):
    headers = _register(client)
    content = b"malicious"

    response = client.post(
        "/api/resumes",
        files={"file": ("../../../etc/evil.pdf", content, "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 201
    file_path = response.json()["version"]["file_path"]

    assert ".." not in file_path
    absolute_path = os.path.join(_STORAGE_ROOT, file_path)
    assert os.path.isfile(absolute_path)
    os.remove(absolute_path)


def test_safe_filename_strips_unsafe_characters():
    assert _safe_filename("../../etc/passwd") == "passwd"
    assert _safe_filename("my resume (final).pdf") == "my_resume__final_.pdf"
    assert _safe_filename(None) == "resume"
    assert _safe_filename("") == "resume"
