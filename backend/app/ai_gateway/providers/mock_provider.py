import json
import logging
from typing import Optional
from .base import AIProvider

logger = logging.getLogger(__name__)


class MockProvider(AIProvider):
    """Mock AI provider for testing and development"""
    
    @property
    def name(self) -> str:
        return "mock"
    
    async def generate(
        self,
        prompt: str,
        model: str = "default",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> str:
        """Generate mock text response"""
        logger.info(f"MockProvider.generate called with prompt length: {len(prompt)}")
        
        # Simple keyword-based responses
        prompt_lower = prompt.lower()
        
        if "classify" in prompt_lower or "category" in prompt_lower:
            return "data_engineering"
        elif "review" in prompt_lower:
            return "passed"
        elif "explain" in prompt_lower:
            return "This is a mock explanation for testing purposes."
        else:
            return "Mock response generated successfully."
    
    async def generate_json(
        self,
        prompt: str,
        schema: dict,
        model: str = "default",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> dict:
        """Generate mock JSON response based on schema and prompt keywords"""
        logger.info(f"MockProvider.generate_json called with schema: {schema.get('title', 'unknown')}")
        
        prompt_lower = prompt.lower()
        schema_title = schema.get("title", "")
        
        # Prefer an exact schema-title match first (this is always available when
        # called via AIGateway.generate_structured, since it derives the title from
        # the requested Pydantic schema). Only fall back to scanning the prompt for
        # keywords when no schema title is provided, so that unrelated keywords
        # appearing incidentally within a prompt (e.g. "matched keywords: ...") don't
        # cause the wrong mock payload to be returned for a different schema.
        if "ExtractedJob" in schema_title:
            return self._mock_extracted_job(prompt)
        elif "JobClassification" in schema_title:
            return self._mock_job_classification(prompt)
        elif "MatchScore" in schema_title:
            return self._mock_match_score(prompt)
        elif "ResumeSelection" in schema_title:
            return self._mock_resume_selection(prompt)
        elif "ResumeTailoring" in schema_title:
            return self._mock_resume_tailoring(prompt)
        elif "ReviewResult" in schema_title:
            return self._mock_review_result(prompt)
        elif "CoverLetterDraft" in schema_title:
            return self._mock_cover_letter(prompt)
        elif "extract" in prompt_lower:
            return self._mock_extracted_job(prompt)
        elif "classify" in prompt_lower:
            return self._mock_job_classification(prompt)
        elif "match" in prompt_lower or "score" in prompt_lower:
            return self._mock_match_score(prompt)
        elif "select resume" in prompt_lower:
            return self._mock_resume_selection(prompt)
        elif "tailor" in prompt_lower:
            return self._mock_resume_tailoring(prompt)
        elif "review" in prompt_lower:
            return self._mock_review_result(prompt)
        else:
            return {"status": "success", "message": "Mock JSON response"}
    
    def _mock_extracted_job(self, prompt: str) -> dict:
        """Return mock extracted job data"""
        return {
            "company": "Acme Corp",
            "title": "Senior Data Engineer",
            "location": "San Francisco, CA",
            "remote_policy": "Hybrid - 3 days in office",
            "salary_min": 150000,
            "salary_max": 200000,
            "required_skills": [
                "Python",
                "SQL",
                "Apache Spark",
                "AWS",
                "Data Modeling"
            ],
            "preferred_skills": [
                "Kafka",
                "Airflow",
                "DBT",
                "Kubernetes"
            ],
            "responsibilities": [
                "Design and build scalable data pipelines",
                "Optimize data warehouse performance",
                "Collaborate with data scientists and analysts",
                "Mentor junior engineers"
            ],
            "experience_years_min": 5
        }
    
    def _mock_job_classification(self, prompt: str) -> dict:
        """Return mock job classification"""
        # Simple keyword detection
        prompt_lower = prompt.lower()
        
        if any(word in prompt_lower for word in ["ml", "machine learning", "ai", "model"]):
            primary = "machine_learning"
        elif any(word in prompt_lower for word in ["data engineer", "pipeline", "etl", "spark"]):
            primary = "data_engineering"
        elif any(word in prompt_lower for word in ["software", "backend", "frontend", "fullstack"]):
            primary = "software_engineering"
        else:
            primary = "data_engineering"
        
        return {
            "primary_category": primary,
            "secondary_categories": ["cloud_infrastructure"],
            "confidence": 0.85,
            "explanation": f"Classified as {primary} based on job requirements and responsibilities."
        }
    
    def _mock_match_score(self, prompt: str) -> dict:
        """Return mock match score"""
        return {
            "overall_score": 78,
            "dimension_scores": {
                "technical_skills": 0.82,
                "experience_level": 0.75,
                "domain_expertise": 0.80,
                "culture_fit": 0.70
            },
            "hard_blockers": [],
            "strong_matches": [
                "5+ years experience with Python and SQL",
                "Proven track record with distributed systems"
            ],
            "missing_info": [
                "No specific Kafka experience mentioned"
            ],
            "recommended_action": "apply_with_standard_resume",
            "explanation": "Strong technical match with relevant experience. Minor gaps in preferred skills can be addressed in cover letter."
        }
    
    def _mock_resume_selection(self, prompt: str) -> dict:
        """Return mock resume selection"""
        # Try to extract resume IDs from prompt
        resume_id = "resume-001"
        if "resume" in prompt.lower():
            # Simple extraction: look for patterns like "resume-xxx" or similar
            import re
            matches = re.findall(r'resume[-_]?\w+', prompt.lower())
            if matches:
                resume_id = matches[0]
        
        return {
            "selected_resume_id": resume_id,
            "selection_rationale": "This resume best highlights relevant data engineering experience and technical skills matching the job requirements.",
            "missing_coverage": ["Kafka experience could be emphasized more"],
            "tailoring_recommended": True
        }
    
    def _mock_resume_tailoring(self, prompt: str) -> dict:
        """Return mock resume tailoring"""
        return {
            "structured_resume": {
                "contact": {
                    "name": "John Doe",
                    "email": "john@example.com",
                    "phone": "555-0123"
                },
                "summary": "Senior Data Engineer with 6+ years building scalable data pipelines",
                "experience": [
                    {
                        "company": "Tech Corp",
                        "title": "Senior Data Engineer",
                        "duration": "2020-Present",
                        "achievements": [
                            "Built real-time data pipeline processing 10M events/day using Spark"
                        ]
                    }
                ],
                "skills": ["Python", "SQL", "Spark", "AWS", "Airflow"]
            },
            "changelog": [
                {
                    "section": "summary",
                    "change_type": "keyword_emphasis",
                    "description": "Added 'scalable data pipelines' to match job requirements"
                }
            ],
            "claim_provenance": [
                {
                    "claim": "Built real-time data pipeline processing 10M events/day",
                    "source_resume_id": "resume-001",
                    "source_section": "experience",
                    "verified": True
                }
            ],
            "keyword_coverage": {
                "Python": True,
                "SQL": True,
                "Apache Spark": True,
                "AWS": True,
                "Kafka": False
            },
            "warnings": []
        }
    
    def _mock_cover_letter(self, prompt: str) -> dict:
        """Return mock cover letter draft"""
        content = (
            "Dear Hiring Manager,\n\n"
            "I am writing to apply for this role. In my previous position, I built "
            "real-time data pipelines that processed millions of events per day, "
            "which directly relates to the scalable systems work described in this "
            "opening. I also led efforts to optimize data warehouse performance, "
            "experience that maps closely to the team's stated need for reliable, "
            "high-throughput infrastructure.\n\n"
            "I would welcome the chance to discuss how my background could "
            "contribute to your team.\n\n"
            "Sincerely,\n[Name]"
        )
        return {
            "content": content,
            "word_count": len(content.split()),
            "warnings": []
        }

    def _mock_review_result(self, prompt: str) -> dict:
        """Return mock review result"""
        return {
            "passed": True,
            "blocking_findings": [],
            "warnings": [],
            "confidence": 0.92
        }
