"""Tests for job matching functionality."""
from __future__ import annotations

import pytest
from uuid import uuid4

from app.agents.matching_agent import MatchingAgent
from app.models import CanonicalJob, Profile, SearchProfile


class TestMatchingAgent:
    """Test MatchingAgent scoring logic."""
    
    def test_skill_match_calculation(self):
        """Test skill matching score calculation."""
        agent = MatchingAgent()
        
        # Mock profile with skills
        profile = Profile(
            id=uuid4(),
            user_id=uuid4(),
            profile_metadata={
                "skills": ["Python", "PostgreSQL", "FastAPI", "Docker"]
            }
        )
        
        # Job with overlapping skills
        job_skills = ["Python", "FastAPI", "AWS", "Kubernetes"]
        
        score = agent._calculate_skill_match(job_skills, profile)
        
        # Should have 50% match (2/4), boosted by 1.2x
        assert score == pytest.approx(60.0, abs=5.0)
    
    def test_skill_match_no_job_skills(self):
        """Test skill match when job has no skills listed."""
        agent = MatchingAgent()
        profile = Profile(
            id=uuid4(),
            user_id=uuid4(),
            profile_metadata={"skills": ["Python"]}
        )
        
        score = agent._calculate_skill_match([], profile)
        assert score == 50.0  # Neutral score
    
    def test_experience_match_sufficient(self):
        """Test experience match when candidate meets requirements."""
        agent = MatchingAgent()
        profile = Profile(
            id=uuid4(),
            user_id=uuid4(),
            profile_metadata={"years_experience": 5}
        )
        
        job_data = {"years_experience": 3}
        score = agent._calculate_experience_match(job_data, profile)
        
        assert score == 100.0
    
    def test_experience_match_insufficient(self):
        """Test experience match when candidate falls short."""
        agent = MatchingAgent()
        profile = Profile(
            id=uuid4(),
            user_id=uuid4(),
            profile_metadata={"years_experience": 2}
        )
        
        job_data = {"years_experience": 5}
        score = agent._calculate_experience_match(job_data, profile)
        
        assert score == 25.0  # Less than 50% of required
    
    def test_seniority_match_exact(self):
        """Test seniority match when levels align."""
        agent = MatchingAgent()
        profile = Profile(
            id=uuid4(),
            user_id=uuid4(),
            target_seniority="Senior"
        )
        
        score = agent._calculate_seniority_match("senior engineer", profile)
        assert score == 100.0
    
    def test_seniority_match_one_level_off(self):
        """Test seniority match when one level apart."""
        agent = MatchingAgent()
        profile = Profile(
            id=uuid4(),
            user_id=uuid4(),
            target_seniority="Mid"
        )
        
        score = agent._calculate_seniority_match("senior", profile)
        assert score == 75.0
    
    def test_hard_blocker_excluded_company(self):
        """Test hard blocker detection for excluded companies."""
        agent = MatchingAgent()
        
        job = CanonicalJob(
            id=uuid4(),
            user_id=uuid4(),
            company="BlockedCorp",
            title="Engineer",
            extracted_data={}
        )
        
        profile = Profile(id=uuid4(), user_id=uuid4())
        
        search_profile = SearchProfile(
            id=uuid4(),
            user_id=uuid4(),
            name="Test",
            excluded_companies=["BlockedCorp", "BadCompany"]
        )
        
        blockers = agent._check_hard_blockers(job, profile, search_profile)
        
        assert len(blockers) == 1
        assert blockers[0]["type"] == "excluded_company"
    
    def test_overall_score_calculation(self):
        """Test overall score weighted calculation."""
        agent = MatchingAgent()
        
        job = CanonicalJob(
            id=uuid4(),
            user_id=uuid4(),
            company="TestCorp",
            title="Senior Python Engineer",
            location="Remote",
            remote_policy="Remote",
            salary_min=120000,
            extracted_data={
                "skills": ["Python", "FastAPI"],
                "seniority_level": "senior",
                "years_experience": 5
            }
        )
        
        profile = Profile(
            id=uuid4(),
            user_id=uuid4(),
            target_seniority="Senior",
            profile_metadata={
                "skills": ["Python", "FastAPI", "PostgreSQL"],
                "years_experience": 6
            }
        )
        
        search_profile = SearchProfile(
            id=uuid4(),
            user_id=uuid4(),
            name="Test",
            remote_policy="Remote",
            min_salary=100000
        )
        
        result = agent.score_job(job, profile, search_profile)
        
        assert "overall_score" in result
        assert result["overall_score"] >= 80  # Should be a strong match
        assert result["overall_score"] <= 100
        assert len(result["hard_blockers"]) == 0
        assert result["recommended_action"] in ["priority", "prepare_application"]
    
    def test_recommended_action_reject(self):
        """Test action recommendation for low scores."""
        agent = MatchingAgent()
        
        action = agent._recommend_action(overall=30, hard_blockers=[], strong_matches=[])
        assert action == "reject"
    
    def test_recommended_action_priority(self):
        """Test action recommendation for high scores."""
        agent = MatchingAgent()
        
        action = agent._recommend_action(overall=85, hard_blockers=[], strong_matches=[{"type": "test"}])
        assert action == "priority"
    
    def test_recommended_action_with_blocker(self):
        """Test action recommendation with hard blockers."""
        agent = MatchingAgent()
        
        action = agent._recommend_action(overall=90, hard_blockers=[{"type": "test"}], strong_matches=[])
        assert action == "reject"
