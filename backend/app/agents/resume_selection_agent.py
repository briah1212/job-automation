from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime

from app.agents.base import BaseAgent
from app.models import CanonicalJob, Profile, ResumeVersion


class ResumeSelectionAgent(BaseAgent):
    """Agent for selecting the best resume for a job application."""
    
    def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute resume selection logic."""
        job = input_data["job"]
        resumes = input_data["resumes"]
        profile = input_data["profile"]
        
        return self.select_resume(job, resumes, profile)
    
    def select_resume(
        self,
        job: CanonicalJob,
        resumes: List[ResumeVersion],
        profile: Profile
    ) -> Dict[str, Any]:
        """Select the best resume for a job and explain the choice."""
        
        if not resumes:
            return {
                "selected_resume_id": None,
                "selection_rationale": "No resumes available in your profile.",
                "alternatives": [],
                "missing_coverage": [],
                "tailoring_recommended": True,
            }
        
        # Score each resume
        scores = []
        for resume in resumes:
            coverage = self._calculate_coverage(resume, job)
            relevance = self._calculate_relevance(resume, job)
            recency = self._calculate_recency(resume)
            performance = self._calculate_performance(resume)
            
            total_score = (
                coverage * 0.40 +
                relevance * 0.30 +
                recency * 0.20 +
                performance * 0.10
            )
            
            scores.append({
                "resume": resume,
                "total_score": total_score,
                "coverage": coverage,
                "relevance": relevance,
                "recency": recency,
                "performance": performance,
            })
        
        # Sort by score
        scores.sort(key=lambda x: x["total_score"], reverse=True)
        best = scores[0]
        
        # Generate rationale
        rationale = self._explain_selection(best, scores)
        
        # Find missing coverage
        missing = self._find_missing_coverage(best["resume"], job)
        
        # Recommend tailoring if score is not excellent
        tailor = best["total_score"] < 0.80
        
        # Format alternatives
        alternatives = [
            {
                "resume_id": str(s["resume"].id),
                "family_name": s["resume"].family.name,
                "version": s["resume"].version,
                "score": round(s["total_score"] * 100),
                "reason": self._summarize_score(s),
            }
            for s in scores[1:3]  # Top 2 alternatives
        ]
        
        return {
            "selected_resume_id": best["resume"].id,
            "selection_rationale": rationale,
            "alternatives": alternatives,
            "missing_coverage": missing,
            "tailoring_recommended": tailor,
        }
    
    def _calculate_coverage(self, resume: ResumeVersion, job: CanonicalJob) -> float:
        """Calculate how well resume covers job requirements (0-1)."""
        job_data = job.extracted_data or {}
        job_skills = set(s.lower() for s in job_data.get("skills", []))
        
        if not job_skills:
            return 0.7  # Neutral if no skills listed
        
        resume_data = resume.parsed_data or {}
        resume_skills = set(s.lower() for s in resume_data.get("skills", []))
        
        if not resume_skills:
            return 0.3  # Low if resume has no skills
        
        # Calculate Jaccard similarity
        intersection = len(job_skills & resume_skills)
        union = len(job_skills | resume_skills)
        
        if union == 0:
            return 0.5
        
        return min(1.0, (intersection / len(job_skills)) * 1.2)  # Boost slightly
    
    def _calculate_relevance(self, resume: ResumeVersion, job: CanonicalJob) -> float:
        """Calculate relevance of resume to job domain (0-1)."""
        resume_data = resume.parsed_data or {}
        family_category = resume.family.target_category or ""
        
        job_data = job.extracted_data or {}
        job_category = job_data.get("category", "").lower()
        
        # Check if categories match
        if family_category.lower() == job_category:
            return 1.0
        
        # Check title similarity
        resume_title = resume_data.get("current_title", "").lower()
        job_title = job.title.lower()
        
        # Simple keyword overlap
        resume_words = set(resume_title.split())
        job_words = set(job_title.split())
        overlap = len(resume_words & job_words)
        
        if overlap >= 2:
            return 0.9
        elif overlap == 1:
            return 0.7
        else:
            return 0.5
    
    def _calculate_recency(self, resume: ResumeVersion) -> float:
        """Calculate recency score (0-1)."""
        age_days = (datetime.utcnow() - resume.created_at).days
        
        if age_days <= 30:
            return 1.0
        elif age_days <= 90:
            return 0.9
        elif age_days <= 180:
            return 0.7
        else:
            return 0.5
    
    def _calculate_performance(self, resume: ResumeVersion) -> float:
        """Calculate performance based on usage stats (0-1)."""
        resume_data = resume.parsed_data or {}
        stats = resume_data.get("usage_stats", {})
        
        interview_rate = stats.get("interview_rate", 0)
        times_used = stats.get("times_used", 0)
        
        if times_used == 0:
            return 0.5  # Neutral for unused resumes
        
        return min(1.0, interview_rate)
    
    def _explain_selection(self, best: Dict, all_scores: List[Dict]) -> str:
        """Generate explanation for resume selection."""
        resume = best["resume"]
        family_name = resume.family.name
        version = resume.version
        
        parts = [
            f"Selected '{family_name}' (v{version}) as the best match.",
            f"Overall fit: {int(best['total_score'] * 100)}%.",
        ]
        
        # Highlight strengths
        if best["coverage"] >= 0.8:
            parts.append("Excellent coverage of required skills.")
        elif best["coverage"] >= 0.6:
            parts.append("Good coverage of required skills.")
        else:
            parts.append("Moderate skill coverage - consider tailoring.")
        
        if best["relevance"] >= 0.8:
            parts.append("Highly relevant to job domain.")
        
        if best["recency"] >= 0.9:
            parts.append("Recently updated.")
        
        # Compare to alternatives
        if len(all_scores) > 1:
            second_best = all_scores[1]
            gap = (best["total_score"] - second_best["total_score"]) * 100
            if gap < 10:
                parts.append(f"Close call - '{second_best['resume'].family.name}' is also viable.")
        
        return " ".join(parts)
    
    def _summarize_score(self, score_data: Dict) -> str:
        """Summarize why a resume scored the way it did."""
        if score_data["coverage"] < 0.5:
            return "Lower skill coverage"
        elif score_data["relevance"] < 0.6:
            return "Less relevant domain"
        elif score_data["recency"] < 0.6:
            return "Older version"
        else:
            return "Solid alternative"
    
    def _find_missing_coverage(self, resume: ResumeVersion, job: CanonicalJob) -> List[str]:
        """Find skills required by job but missing from resume."""
        job_data = job.extracted_data or {}
        job_skills = set(s.lower() for s in job_data.get("skills", []))
        
        resume_data = resume.parsed_data or {}
        resume_skills = set(s.lower() for s in resume_data.get("skills", []))
        
        missing = job_skills - resume_skills
        return sorted(list(missing))[:5]  # Top 5 missing skills
