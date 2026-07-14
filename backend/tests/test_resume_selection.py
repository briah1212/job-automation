"""Tests for resume selection functionality."""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from app.agents.resume_selection_agent import ResumeSelectionAgent
from app.models import CanonicalJob, Profile, ResumeFamily, ResumeVersion


class TestResumeSelectionAgent:
    """Test ResumeSelectionAgent logic."""
    
    def test_coverage_calculation_high(self):
        """Test coverage when resume matches job skills well."""
        agent = ResumeSelectionAgent()
        
        job = CanonicalJob(
            id=uuid4(),
            user_id=uuid4(),
            company="TestCorp",
            title="Engineer",
            extracted_data={
                "skills": ["Python", "FastAPI", "PostgreSQL"]
            }
        )
        
        resume = ResumeVersion(
            id=uuid4(),
            family_id=uuid4(),
            version=1,
            parsed_data={
                "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"]
            }
        )
        resume.family = ResumeFamily(id=uuid4(), user_id=uuid4(), name="Test")
        
        coverage = agent._calculate_coverage(resume, job)
        
        assert coverage >= 1.0  # 100% coverage (3/3 job skills), boosted
    
    def test_coverage_calculation_partial(self):
        """Test coverage with partial skill match."""
        agent = ResumeSelectionAgent()
        
        job = CanonicalJob(
            id=uuid4(),
            user_id=uuid4(),
            company="TestCorp",
            title="Engineer",
            extracted_data={
                "skills": ["Python", "Java", "Kubernetes", "AWS"]
            }
        )
        
        resume = ResumeVersion(
            id=uuid4(),
            family_id=uuid4(),
            version=1,
            parsed_data={
                "skills": ["Python", "Docker"]
            }
        )
        resume.family = ResumeFamily(id=uuid4(), user_id=uuid4(), name="Test")
        
        coverage = agent._calculate_coverage(resume, job)
        
        # 1/4 = 25%, boosted by 1.2x = 30%
        assert coverage == pytest.approx(0.30, abs=0.05)
    
    def test_recency_calculation_recent(self):
        """Test recency score for recent resume."""
        agent = ResumeSelectionAgent()
        
        resume = ResumeVersion(
            id=uuid4(),
            family_id=uuid4(),
            version=1,
            created_at=datetime.utcnow() - timedelta(days=15)
        )
        
        score = agent._calculate_recency(resume)
        assert score == 1.0
    
    def test_recency_calculation_old(self):
        """Test recency score for old resume."""
        agent = ResumeSelectionAgent()
        
        resume = ResumeVersion(
            id=uuid4(),
            family_id=uuid4(),
            version=1,
            created_at=datetime.utcnow() - timedelta(days=200)
        )
        
        score = agent._calculate_recency(resume)
        assert score == 0.5
    
    def test_select_best_resume(self):
        """Test selecting the best resume from multiple options."""
        agent = ResumeSelectionAgent()
        
        job = CanonicalJob(
            id=uuid4(),
            user_id=uuid4(),
            company="TestCorp",
            title="Python Engineer",
            extracted_data={
                "skills": ["Python", "FastAPI", "PostgreSQL"],
                "category": "software_engineering"
            }
        )
        
        # Resume 1: High coverage, recent
        family1 = ResumeFamily(
            id=uuid4(),
            user_id=uuid4(),
            name="Software Engineer Resume",
            target_category="software_engineering"
        )
        resume1 = ResumeVersion(
            id=uuid4(),
            family_id=family1.id,
            version=1,
            created_at=datetime.utcnow() - timedelta(days=10),
            parsed_data={
                "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
                "current_title": "Python Engineer"
            }
        )
        resume1.family = family1
        
        # Resume 2: Lower coverage, older
        family2 = ResumeFamily(
            id=uuid4(),
            user_id=uuid4(),
            name="General Resume",
            target_category="general"
        )
        resume2 = ResumeVersion(
            id=uuid4(),
            family_id=family2.id,
            version=1,
            created_at=datetime.utcnow() - timedelta(days=100),
            parsed_data={
                "skills": ["Python", "Django"],
                "current_title": "Developer"
            }
        )
        resume2.family = family2
        
        profile = Profile(id=uuid4(), user_id=uuid4())
        
        result = agent.select_resume(job, [resume1, resume2], profile)
        
        assert result["selected_resume_id"] == resume1.id
        assert "selection_rationale" in result
        assert len(result["alternatives"]) >= 1
        assert isinstance(result["tailoring_recommended"], bool)
    
    def test_select_resume_no_resumes(self):
        """Test resume selection with no available resumes."""
        agent = ResumeSelectionAgent()
        
        job = CanonicalJob(
            id=uuid4(),
            user_id=uuid4(),
            company="TestCorp",
            title="Engineer",
            extracted_data={}
        )
        
        profile = Profile(id=uuid4(), user_id=uuid4())
        
        result = agent.select_resume(job, [], profile)
        
        assert result["selected_resume_id"] is None
        assert "No resumes available" in result["selection_rationale"]
        assert result["tailoring_recommended"] is True
    
    def test_missing_coverage_identification(self):
        """Test identification of missing skills."""
        agent = ResumeSelectionAgent()
        
        job = CanonicalJob(
            id=uuid4(),
            user_id=uuid4(),
            company="TestCorp",
            title="Engineer",
            extracted_data={
                "skills": ["Python", "Kubernetes", "AWS", "Terraform", "Go"]
            }
        )
        
        resume = ResumeVersion(
            id=uuid4(),
            family_id=uuid4(),
            version=1,
            parsed_data={
                "skills": ["Python", "Docker"]
            }
        )
        resume.family = ResumeFamily(id=uuid4(), user_id=uuid4(), name="Test")
        
        missing = agent._find_missing_coverage(resume, job)
        
        assert len(missing) <= 5  # Top 5
        assert "kubernetes" in missing
        assert "aws" in missing
        assert "python" not in missing  # Should not include matched skills
