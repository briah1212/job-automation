"""Tests for resume PDF rendering and diffing services."""
from __future__ import annotations

import os
import shutil
import tempfile
from uuid import uuid4

import pytest

from app.models import ResumeFamily, ResumeVersion
from app.services.resume_diff import compute_resume_diff
from app.services.resume_rendering import render_resume_pdf


class TestRenderResumePdf:
    """Tests for render_resume_pdf."""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_render_writes_real_pdf_file(self):
        version = ResumeVersion(
            id=uuid4(),
            family_id=uuid4(),
            version=1,
            parsed_data={
                "summary": "Experienced software engineer with a focus on backend systems.",
                "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
                "experience": [
                    {
                        "title": "Senior Engineer",
                        "company": "Acme Corp",
                        "dates": "2020-2024",
                        "bullets": [
                            "Led migration to microservices architecture",
                            "Reduced API latency by 40%",
                        ],
                    },
                    "Software Engineer at Beta Inc, 2018-2020",
                ],
            },
        )

        output_path = os.path.join(self.tmp_dir, "resume.pdf")
        page_count = render_resume_pdf(version, output_path)

        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 0
        assert isinstance(page_count, int)
        assert page_count >= 1

    def test_render_creates_parent_directories(self):
        version = ResumeVersion(
            id=uuid4(),
            family_id=uuid4(),
            version=1,
            parsed_data={"summary": "Minimal resume.", "skills": [], "experience": []},
        )

        output_path = os.path.join(self.tmp_dir, "nested", "dir", "resume.pdf")
        page_count = render_resume_pdf(version, output_path)

        assert os.path.exists(output_path)
        assert page_count >= 1

    def test_render_handles_missing_parsed_data_fields(self):
        version = ResumeVersion(
            id=uuid4(),
            family_id=uuid4(),
            version=1,
            parsed_data={},
        )

        output_path = os.path.join(self.tmp_dir, "empty.pdf")
        page_count = render_resume_pdf(version, output_path)

        assert os.path.exists(output_path)
        assert page_count >= 1


class TestComputeResumeDiff:
    """Tests for compute_resume_diff."""

    def _make_version(self, parsed_data: dict) -> ResumeVersion:
        family = ResumeFamily(id=uuid4(), user_id=uuid4(), name="Test")
        version = ResumeVersion(
            id=uuid4(), family_id=family.id, version=1, parsed_data=parsed_data
        )
        version.family = family
        return version

    def test_detects_added_and_removed_skills(self):
        base = self._make_version(
            {
                "summary": "Backend engineer.",
                "skills": ["Python", "Django", "PostgreSQL"],
                "experience": [],
            }
        )
        new = self._make_version(
            {
                "summary": "Backend engineer.",
                "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
                "experience": [],
            }
        )

        diff = compute_resume_diff(base, new)

        assert set(diff["skills_change"]["added"]) == {"FastAPI", "Docker"}
        assert set(diff["skills_change"]["removed"]) == {"Django"}
        assert "FastAPI" in diff["added"]
        assert "Django" in diff["removed"]
        assert diff["keyword_changes"]["added"] == diff["skills_change"]["added"]
        assert diff["keyword_changes"]["removed"] == diff["skills_change"]["removed"]

    def test_detects_skill_reordering(self):
        base = self._make_version({"skills": ["Python", "Docker", "AWS"]})
        new = self._make_version({"skills": ["AWS", "Python", "Docker"]})

        diff = compute_resume_diff(base, new)

        assert diff["skills_change"]["added"] == []
        assert diff["skills_change"]["removed"] == []
        assert diff["skills_change"]["reordered"] == ["AWS", "Python", "Docker"]

    def test_summary_change_reports_before_and_after(self):
        base = self._make_version({"summary": "Junior developer."})
        new = self._make_version({"summary": "Senior developer with leadership experience."})

        diff = compute_resume_diff(base, new)

        assert diff["summary_change"]["before"] == "Junior developer."
        assert diff["summary_change"]["after"] == "Senior developer with leadership experience."
        assert len(diff["summary_change"]["diff_lines"]) > 0

    def test_warns_about_missing_fields(self):
        base = self._make_version({"summary": "A", "skills": [], "certifications": ["AWS CCP"]})
        new = self._make_version({"summary": "A", "skills": []})

        diff = compute_resume_diff(base, new)

        assert any("certifications" in w for w in diff["warnings"])
