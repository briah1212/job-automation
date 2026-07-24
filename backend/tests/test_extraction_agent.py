"""Tests for the extraction/classification agents, seniority heuristic, and worker."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.agents.classification_agent import ClassificationAgent
from app.agents.extraction_agent import ExtractionAgent
from app.models import CanonicalJob, JobStatus, User, WorkflowStatus, WorkflowTask
from app.services.seniority_heuristic import infer_seniority
from worker import process_extraction_task


class TestExtractionAgent:
    """Tests for ExtractionAgent.extract() against the mock provider."""

    @pytest.mark.asyncio
    async def test_extract_returns_expected_field_shape(self):
        agent = ExtractionAgent()
        result = await agent.extract(
            raw_text="We are hiring a Senior Data Engineer at Acme Corp in San Francisco.",
            source_url="https://example.com/jobs/1",
            user_id=str(uuid4()),
        )

        assert result["company"]
        assert result["title"]
        assert isinstance(result["required_skills"], list)
        assert isinstance(result["preferred_skills"], list)
        assert isinstance(result["responsibilities"], list)
        assert "location" in result
        assert "remote_policy" in result
        assert "salary_min" in result
        assert "salary_max" in result
        assert "experience_years_min" in result

    @pytest.mark.asyncio
    async def test_extract_truncates_long_raw_text(self):
        agent = ExtractionAgent()
        long_text = "x" * 50000
        # Should not raise despite an oversized input, since it gets truncated
        # before being embedded in the prompt.
        result = await agent.extract(
            raw_text=long_text,
            source_url=None,
            user_id=str(uuid4()),
        )
        assert result["company"]


class TestClassificationAgent:
    """Tests for ClassificationAgent.classify() against the mock provider."""

    @pytest.mark.asyncio
    async def test_classify_returns_expected_field_shape(self):
        agent = ClassificationAgent()
        result = await agent.classify(
            title="Senior Data Engineer",
            responsibilities=["Design and build scalable data pipelines"],
            user_id=str(uuid4()),
        )

        assert result["primary_category"]
        assert isinstance(result["secondary_categories"], list)
        assert isinstance(result["confidence"], float)
        assert result["explanation"]

    @pytest.mark.asyncio
    async def test_classify_detects_software_engineering_keywords(self):
        agent = ClassificationAgent()
        result = await agent.classify(
            title="Backend Software Engineer",
            # Note: avoid substrings like "ai"/"ml" (e.g. in "maintain") which the
            # mock provider's crude keyword scan would misclassify as machine_learning.
            responsibilities=["Build and support backend services and APIs"],
            user_id=str(uuid4()),
        )
        assert result["primary_category"] == "software_engineering"


class TestInferSeniority:
    """Tests for the infer_seniority heuristic."""

    def test_senior_title(self):
        assert infer_seniority("Senior Software Engineer", None) == "senior"

    def test_staff_title(self):
        assert infer_seniority("Staff Data Engineer", None) == "staff"

    def test_principal_title(self):
        assert infer_seniority("Principal Engineer", None) == "staff"

    def test_junior_title(self):
        assert infer_seniority("Junior Developer", None) == "entry"

    def test_lead_title(self):
        assert infer_seniority("Engineering Manager", None) == "lead"

    def test_no_title_low_experience(self):
        assert infer_seniority("", 1) == "entry"

    def test_no_title_mid_experience(self):
        assert infer_seniority("", 3) == "mid"

    def test_no_title_high_experience(self):
        assert infer_seniority("", 6) == "senior"

    def test_no_title_very_high_experience(self):
        assert infer_seniority("", 9) == "staff"

    def test_no_title_no_experience_defaults_to_mid(self):
        assert infer_seniority("", None) == "mid"

    def test_title_keyword_takes_priority_over_experience(self):
        # Even with low experience_years_min, an explicit "senior" in the title wins.
        assert infer_seniority("Senior Engineer", 1) == "senior"


class TestProcessExtractionTask:
    """Tests for worker.process_extraction_task, mocking the external HTTP fetch."""

    def _make_user_and_job(self, db):
        user = User(id=uuid4(), email=f"{uuid4()}@example.com", hashed_password="hashed")
        db.add(user)
        db.commit()

        job = CanonicalJob(
            id=uuid4(),
            user_id=user.id,
            company="",
            title="",
            status=JobStatus.extracting,
            extracted_data={"url": "https://example.com/jobs/42"},
        )
        db.add(job)
        db.commit()
        return user, job

    @pytest.mark.asyncio
    async def test_process_extraction_task_populates_job_and_completes_task(self, db):
        user, job = self._make_user_and_job(db)

        task = WorkflowTask(
            workflow_type="job_extraction",
            entity_id=job.id,
            status=WorkflowStatus.running,
        )
        db.add(task)
        db.commit()

        mock_response = AsyncMock()
        mock_response.text = "<html><body><h1>Senior Data Engineer</h1><p>Great job.</p></body></html>"
        mock_response.status_code = 200
        mock_response.raise_for_status = lambda: None

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
            await process_extraction_task(task, db)
            db.commit()

        db.refresh(job)
        db.refresh(task)

        assert task.status == WorkflowStatus.completed
        assert task.completed_at is not None

        assert job.company
        assert job.title
        assert job.status == JobStatus.scored

        extracted_data = job.extracted_data
        assert extracted_data["url"] == "https://example.com/jobs/42"
        assert "skills" in extracted_data
        assert isinstance(extracted_data["skills"], list)
        assert "requirements" in extracted_data
        assert "category" in extracted_data
        assert "secondary_categories" in extracted_data
        assert "seniority_level" in extracted_data
        assert extracted_data["raw_text_length"] > 0

    @pytest.mark.asyncio
    async def test_process_extraction_task_handles_fetch_failure_gracefully(self, db):
        user, job = self._make_user_and_job(db)

        task = WorkflowTask(
            workflow_type="job_extraction",
            entity_id=job.id,
            status=WorkflowStatus.running,
        )
        db.add(task)
        db.commit()

        # Simulates total fetch failure: both the direct httpx GET and the
        # browser-render fallback (worker._fetch_via_browser) fail. Without
        # mocking the fallback too, this would make a real network call to
        # the render server/example.com and mask the scenario under test.
        with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=Exception("connection refused"))), \
                patch("worker._fetch_via_browser", new=AsyncMock(return_value=("", False))):
            await process_extraction_task(task, db)
            db.commit()

        db.refresh(job)
        db.refresh(task)

        # A fetch failure should not crash the task - it should still complete
        # (with sparse data) rather than being marked failed.
        assert task.status == WorkflowStatus.completed
        assert job.extracted_data.get("fetch_warning")

    @pytest.mark.asyncio
    async def test_process_extraction_task_falls_back_to_browser_render_on_thin_content(self, db):
        """A plain httpx GET against a client-rendered SPA (Ashby, Workday,
        etc.) routinely succeeds with a 200 but near-empty body - the real
        content only exists after JS execution. Confirmed live this session
        against a real Workday posting: the direct fetch returned nothing
        useful while a real browser render returned the full description.
        worker._fetch_raw_text should treat that thin result as a fetch
        failure and fall back to _fetch_via_browser rather than reporting
        success with near-nothing to show for it."""
        user, job = self._make_user_and_job(db)

        task = WorkflowTask(
            workflow_type="job_extraction",
            entity_id=job.id,
            status=WorkflowStatus.running,
        )
        db.add(task)
        db.commit()

        mock_response = AsyncMock()
        mock_response.text = "<html><body>Loading...</body></html>"
        mock_response.status_code = 200
        mock_response.raise_for_status = lambda: None

        rendered_text = (
            "Senior Data Engineer at Example Corp. " + "Great job with real responsibilities. " * 10
        )

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)), \
                patch("worker._fetch_via_browser", new=AsyncMock(return_value=(rendered_text, True))):
            await process_extraction_task(task, db)
            db.commit()

        db.refresh(job)
        db.refresh(task)

        assert task.status == WorkflowStatus.completed
        assert not job.extracted_data.get("fetch_warning")
        assert job.extracted_data["raw_text_length"] == len(rendered_text)

    @pytest.mark.asyncio
    async def test_process_extraction_task_falls_back_when_content_is_an_iframe_shell(self, db):
        """A plain httpx GET can return plenty of TEXT (past
        _THIN_CONTENT_CHARS) while still containing none of the real job
        content, if the real content is loaded into a same-page <iframe>
        via a separate HTTP request the plain fetch never makes. Confirmed
        live against a real iCIMS posting (careers-gdms.icims.com): the
        fetched page was several hundred KB of genuine site nav/chrome, with
        the actual job title/location/description entirely inside
        <iframe id="icims_content_iframe">. worker._fetch_raw_text must
        treat this the same as thin content - falling back to a real
        browser render - rather than confidently reporting fetch success on
        page chrome with zero job details."""
        user, job = self._make_user_and_job(db)

        task = WorkflowTask(
            workflow_type="job_extraction",
            entity_id=job.id,
            status=WorkflowStatus.running,
        )
        db.add(task)
        db.commit()

        # Long enough to clear _THIN_CONTENT_CHARS on its own - the point is
        # this alone must NOT be treated as success once the iframe marker
        # is present.
        shell_html = (
            "<html><body><nav>Site Navigation Chrome</nav>"
            + "Padding text so this clears the thin-content threshold. " * 10
            + '<iframe id="icims_content_iframe" src="/jobs/1/job?in_iframe=1"></iframe>'
            + "</body></html>"
        )
        mock_response = AsyncMock()
        mock_response.text = shell_html
        mock_response.status_code = 200
        mock_response.raise_for_status = lambda: None

        rendered_text = (
            "UC Telephony Software Engineer US-MA-Dedham. " + "Real job description content. " * 10
        )

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)), \
                patch("worker._fetch_via_browser", new=AsyncMock(return_value=(rendered_text, True))):
            await process_extraction_task(task, db)
            db.commit()

        db.refresh(job)
        db.refresh(task)

        assert task.status == WorkflowStatus.completed
        assert not job.extracted_data.get("fetch_warning")
        assert job.extracted_data["raw_text_length"] == len(rendered_text)

    @pytest.mark.asyncio
    async def test_process_extraction_task_preserves_authoritative_company_and_title(self, db):
        """A job discovered via a company watch already has real company/
        title/location straight from the ATS's own API - the extraction
        agent (especially AI_PROVIDER=mock, which returns a fixed canned
        response regardless of input - confirmed live) must not clobber
        them with a worse guess."""
        user = User(id=uuid4(), email=f"{uuid4()}@example.com", hashed_password="hashed")
        db.add(user)
        db.commit()

        job = CanonicalJob(
            id=uuid4(),
            user_id=user.id,
            company="Airtable",
            title="Software Engineer, Data",
            location="New York, NY",
            status=JobStatus.discovered,
            extracted_data={
                "url": "https://job-boards.greenhouse.io/airtable/jobs/8124953002",
                "source": "company_watch",
                "raw_content": "We are hiring a Senior Data Engineer at Acme Corp in San Francisco.",
            },
        )
        db.add(job)
        db.commit()

        task = WorkflowTask(workflow_type="job_extraction", entity_id=job.id, status=WorkflowStatus.running)
        db.add(task)
        db.commit()

        await process_extraction_task(task, db)
        db.commit()
        db.refresh(job)

        assert job.company == "Airtable"
        assert job.title == "Software Engineer, Data"
        assert job.location == "New York, NY"
