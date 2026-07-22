"""Tests for the public-ATS-job-board discovery fetchers.

Mocks httpx.AsyncClient.get directly (no mock-HTTP dependency installed) with
response payload shapes captured live from the real Greenhouse/Lever/Ashby
public APIs while building this - not guessed schemas.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.job_discovery import fetch_ashby_jobs, fetch_greenhouse_jobs, fetch_jobs_for_watch, fetch_lever_jobs


def _mock_response(payload):
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status = MagicMock()
    return response


@pytest.mark.asyncio
async def test_fetch_greenhouse_jobs_normalizes_real_shape():
    payload = {
        "jobs": [
            {
                "id": 8391589002,
                "title": "Account Executive, SLED",
                "location": {"name": "Austin, TX; Remote - US"},
                "absolute_url": "https://job-boards.greenhouse.io/airtable/jobs/8391589002",
                "content": "&lt;div&gt;&lt;p&gt;Airtable is the no-code app platform&lt;/p&gt;&lt;/div&gt;",
            }
        ]
    }
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_mock_response(payload))):
        jobs = await fetch_greenhouse_jobs("airtable")

    assert len(jobs) == 1
    job = jobs[0]
    assert job["external_id"] == "8391589002"
    assert job["title"] == "Account Executive, SLED"
    assert job["location"] == "Austin, TX; Remote - US"
    assert job["url"] == "https://job-boards.greenhouse.io/airtable/jobs/8391589002"
    assert "Airtable is the no-code app platform" in job["raw_content"]
    assert "&lt;" not in job["raw_content"] and "<div>" not in job["raw_content"]


@pytest.mark.asyncio
async def test_fetch_lever_jobs_normalizes_real_shape():
    payload = [
        {
            "id": "ac978161-6f46-4f6b-ad9e-a258e642751c",
            "text": "Administrative Business Partner",
            "categories": {"location": "London, United Kingdom", "commitment": "Full-time"},
            "hostedUrl": "https://jobs.lever.co/palantir/ac978161-6f46-4f6b-ad9e-a258e642751c",
            "descriptionPlain": "Life at Palantir...",
        }
    ]
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_mock_response(payload))):
        jobs = await fetch_lever_jobs("palantir")

    assert len(jobs) == 1
    job = jobs[0]
    assert job["external_id"] == "ac978161-6f46-4f6b-ad9e-a258e642751c"
    assert job["title"] == "Administrative Business Partner"
    assert job["location"] == "London, United Kingdom"
    assert job["raw_content"] == "Life at Palantir..."


@pytest.mark.asyncio
async def test_fetch_ashby_jobs_normalizes_real_shape():
    payload = {
        "jobs": [
            {
                "id": "2ca70e4e-c92d-45f8-9af3-117567200348",
                "title": "Senior Software Engineer",
                "location": "NYC Office",
                "jobUrl": "https://jobs.ashbyhq.com/confido/2ca70e4e-c92d-45f8-9af3-117567200348",
                "descriptionHtml": '<p style="min-height:1.5em">Confido is the AI infrastructure</p>',
            }
        ],
        "apiVersion": 1,
    }
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_mock_response(payload))):
        jobs = await fetch_ashby_jobs("confido")

    assert len(jobs) == 1
    job = jobs[0]
    assert job["external_id"] == "2ca70e4e-c92d-45f8-9af3-117567200348"
    assert job["title"] == "Senior Software Engineer"
    assert job["location"] == "NYC Office"
    assert "Confido is the AI infrastructure" in job["raw_content"]
    assert "<p" not in job["raw_content"]


@pytest.mark.asyncio
async def test_fetch_jobs_for_watch_dispatches_by_platform():
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_mock_response({"jobs": []}))):
        jobs = await fetch_jobs_for_watch("greenhouse", "airtable")
    assert jobs == []


@pytest.mark.asyncio
async def test_fetch_jobs_for_watch_rejects_unsupported_platform():
    with pytest.raises(ValueError, match="Unsupported ats_platform"):
        await fetch_jobs_for_watch("workday", "some-tenant")
