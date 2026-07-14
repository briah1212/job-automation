from __future__ import annotations

from typing import Any, Dict, List, Optional
import re

from app.agents.base import BaseAgent
from app.models import CanonicalJob, Profile, ResumeVersion, SearchProfile


class MatchingAgent(BaseAgent):
    """Agent for matching jobs to user profiles and calculating match scores."""
    
    def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute matching logic."""
        job = input_data["job"]
        profile = input_data["profile"]
        search_profile = input_data.get("search_profile")
        
        return self.score_job(job, profile, search_profile)
    
    def score_job(
        self,
        job: CanonicalJob,
        profile: Profile,
        search_profile: Optional[SearchProfile] = None
    ) -> Dict[str, Any]:
        """Calculate comprehensive match score for a job."""
        
        # Extract job data
        job_data = job.extracted_data or {}
        job_skills = job_data.get("skills", [])
        job_seniority = job_data.get("seniority_level", "").lower()
        job_remote = (job.remote_policy or "").lower()
        
        # Calculate dimension scores
        skill_score = self._calculate_skill_match(job_skills, profile)
        experience_score = self._calculate_experience_match(job_data, profile)
        seniority_score = self._calculate_seniority_match(job_seniority, profile)
        location_score = self._calculate_location_match(job, profile, search_profile)
        salary_score = self._calculate_salary_match(job, search_profile)
        
        # Check hard blockers
        hard_blockers = self._check_hard_blockers(job, profile, search_profile)
        
        # Find strong matches
        strong_matches = self._find_strong_matches(job, profile, job_skills)
        
        # Identify soft gaps
        soft_gaps = self._find_soft_gaps(job, profile, job_skills)
        
        # Identify missing information
        missing_info = self._find_missing_info(job)
        
        # Calculate overall score (weighted average)
        if hard_blockers:
            overall = 0  # Hard blockers = auto-reject
        else:
            overall = int(
                skill_score * 0.35 +
                experience_score * 0.25 +
                seniority_score * 0.15 +
                location_score * 0.15 +
                salary_score * 0.10
            )
        
        # Generate explanation
        explanation = self._generate_explanation(
            overall, skill_score, experience_score, seniority_score,
            location_score, salary_score, hard_blockers, strong_matches
        )
        
        # Determine recommended action
        action = self._recommend_action(overall, hard_blockers, strong_matches)
        
        return {
            "overall_score": overall,
            "skill_score": skill_score,
            "experience_score": experience_score,
            "seniority_score": seniority_score,
            "location_score": location_score,
            "salary_score": salary_score,
            "hard_blockers": hard_blockers,
            "strong_matches": strong_matches,
            "soft_gaps": soft_gaps,
            "missing_info": missing_info,
            "explanation": explanation,
            "recommended_action": action,
        }
    
    def _calculate_skill_match(self, job_skills: List[str], profile: Profile) -> float:
        """Calculate skill match score (0-100)."""
        if not job_skills:
            return 50.0  # Neutral if no skills listed
        
        profile_metadata = profile.profile_metadata or {}
        profile_skills = profile_metadata.get("skills", [])
        
        if not profile_skills:
            return 30.0  # Low score if profile has no skills
        
        # Normalize skills for comparison
        job_skills_norm = [s.lower().strip() for s in job_skills]
        profile_skills_norm = [s.lower().strip() for s in profile_skills]
        
        # Calculate match
        matched = sum(1 for js in job_skills_norm if any(ps in js or js in ps for ps in profile_skills_norm))
        match_rate = matched / len(job_skills_norm)
        
        return min(100.0, match_rate * 100 * 1.2)  # Boost slightly
    
    def _calculate_experience_match(self, job_data: Dict, profile: Profile) -> float:
        """Calculate experience match score (0-100)."""
        required_years = job_data.get("years_experience")
        if not required_years:
            return 70.0  # Neutral if not specified
        
        profile_metadata = profile.profile_metadata or {}
        total_years = profile_metadata.get("years_experience", 0)
        
        if total_years >= required_years:
            return 100.0
        elif total_years >= required_years * 0.7:
            return 75.0
        elif total_years >= required_years * 0.5:
            return 50.0
        else:
            return 25.0
    
    def _calculate_seniority_match(self, job_seniority: str, profile: Profile) -> float:
        """Calculate seniority level match score (0-100)."""
        if not job_seniority:
            return 70.0
        
        target = (profile.target_seniority or "").lower()
        if not target:
            return 70.0
        
        # Seniority hierarchy
        levels = ["entry", "junior", "mid", "senior", "staff", "principal", "lead"]
        
        try:
            job_idx = next(i for i, l in enumerate(levels) if l in job_seniority)
            target_idx = next(i for i, l in enumerate(levels) if l in target)
            diff = abs(job_idx - target_idx)
            
            if diff == 0:
                return 100.0
            elif diff == 1:
                return 75.0
            elif diff == 2:
                return 50.0
            else:
                return 25.0
        except StopIteration:
            return 70.0  # Neutral if can't determine
    
    def _calculate_location_match(
        self,
        job: CanonicalJob,
        profile: Profile,
        search_profile: Optional[SearchProfile]
    ) -> float:
        """Calculate location match score (0-100)."""
        remote = (job.remote_policy or "").lower()
        
        if "remote" in remote or "worldwide" in remote:
            return 100.0
        
        if search_profile and search_profile.remote_policy:
            pref = search_profile.remote_policy.lower()
            if pref == "remote" and "remote" not in remote:
                return 20.0
            elif pref == "onsite" and "onsite" in remote:
                return 100.0
            elif pref == "hybrid":
                return 90.0 if "hybrid" in remote else 60.0
        
        return 70.0  # Neutral default
    
    def _calculate_salary_match(self, job: CanonicalJob, search_profile: Optional[SearchProfile]) -> float:
        """Calculate salary match score (0-100)."""
        if not search_profile or not search_profile.min_salary:
            return 70.0
        
        if job.salary_min and job.salary_min >= search_profile.min_salary:
            return 100.0
        elif job.salary_max and job.salary_max >= search_profile.min_salary:
            return 80.0
        elif not job.salary_min and not job.salary_max:
            return 50.0  # Unknown salary
        else:
            return 20.0  # Below minimum
    
    def _check_hard_blockers(
        self,
        job: CanonicalJob,
        profile: Profile,
        search_profile: Optional[SearchProfile]
    ) -> List[Dict[str, str]]:
        """Check for hard blocking criteria."""
        blockers = []
        
        # Check excluded companies
        if search_profile and search_profile.excluded_companies:
            if job.company in search_profile.excluded_companies:
                blockers.append({
                    "type": "excluded_company",
                    "reason": f"Company '{job.company}' is in your exclusion list"
                })
        
        # Check work authorization
        job_data = job.extracted_data or {}
        if job_data.get("requires_sponsorship") is False:
            auth = (profile.work_authorization or "").lower()
            if "requires" in auth or "visa" in auth:
                blockers.append({
                    "type": "work_authorization",
                    "reason": "Job does not offer visa sponsorship"
                })
        
        return blockers
    
    def _find_strong_matches(self, job: CanonicalJob, profile: Profile, job_skills: List[str]) -> List[Dict[str, str]]:
        """Find strong positive match signals."""
        matches = []
        profile_metadata = profile.profile_metadata or {}
        
        # Check for exact title match
        if profile_metadata.get("current_title"):
            if profile_metadata["current_title"].lower() in job.title.lower():
                matches.append({
                    "type": "title_match",
                    "detail": f"Your current title '{profile_metadata['current_title']}' matches job title"
                })
        
        # Check for skill overlap
        profile_skills = profile_metadata.get("skills", [])
        if job_skills and profile_skills:
            overlap = set(s.lower() for s in job_skills) & set(s.lower() for s in profile_skills)
            if len(overlap) >= 5:
                matches.append({
                    "type": "high_skill_overlap",
                    "detail": f"{len(overlap)} matching skills"
                })
        
        return matches
    
    def _find_soft_gaps(self, job: CanonicalJob, profile: Profile, job_skills: List[str]) -> List[Dict[str, str]]:
        """Find soft gaps that are not blockers."""
        gaps = []
        profile_metadata = profile.profile_metadata or {}
        profile_skills = [s.lower() for s in profile_metadata.get("skills", [])]
        
        # Missing skills
        if job_skills:
            missing = [s for s in job_skills if s.lower() not in profile_skills]
            if missing and len(missing) <= 3:
                gaps.append({
                    "type": "missing_skills",
                    "detail": f"Missing skills: {', '.join(missing[:3])}"
                })
        
        return gaps
    
    def _find_missing_info(self, job: CanonicalJob) -> List[Dict[str, str]]:
        """Identify missing job information."""
        missing = []
        
        if not job.salary_min and not job.salary_max:
            missing.append({"field": "salary", "impact": "Cannot assess compensation fit"})
        
        if not job.remote_policy:
            missing.append({"field": "remote_policy", "impact": "Cannot assess location fit"})
        
        job_data = job.extracted_data or {}
        if not job_data.get("skills"):
            missing.append({"field": "skills", "impact": "Cannot fully assess technical fit"})
        
        return missing
    
    def _generate_explanation(
        self,
        overall: int,
        skill_score: float,
        experience_score: float,
        seniority_score: float,
        location_score: float,
        salary_score: float,
        hard_blockers: List,
        strong_matches: List
    ) -> str:
        """Generate human-readable explanation."""
        if hard_blockers:
            return f"This job has {len(hard_blockers)} blocking issue(s): " + \
                   "; ".join(b["reason"] for b in hard_blockers)
        
        parts = [f"Overall match: {overall}/100."]
        
        if strong_matches:
            parts.append(f"Strong signals: {len(strong_matches)} positive indicators.")
        
        # Highlight best and worst dimensions
        scores = {
            "Skills": skill_score,
            "Experience": experience_score,
            "Seniority": seniority_score,
            "Location": location_score,
            "Salary": salary_score,
        }
        best = max(scores, key=scores.get)
        worst = min(scores, key=scores.get)
        
        parts.append(f"Strongest: {best} ({scores[best]:.0f}/100).")
        parts.append(f"Weakest: {worst} ({scores[worst]:.0f}/100).")
        
        return " ".join(parts)
    
    def _recommend_action(self, overall: int, hard_blockers: List, strong_matches: List) -> str:
        """Recommend action based on score."""
        if hard_blockers:
            return "reject"
        elif overall >= 80:
            return "priority"
        elif overall >= 60:
            return "prepare_application"
        elif overall >= 40:
            return "save_for_later"
        else:
            return "reject"
