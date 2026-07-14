#!/usr/bin/env python3
"""
Quick test to verify AI Gateway works correctly
Run from: /home/brian/job_automation/backend
"""
import asyncio
import sys
sys.path.insert(0, '/home/brian/job_automation/backend')

from app.ai_gateway import AIGateway
from app.ai_gateway.schemas import ExtractedJob, JobClassification, MatchScore


async def test_gateway():
    print("=== Testing AI Gateway ===\n")
    
    # Initialize with mock provider
    gateway = AIGateway(provider="mock")
    print(f"✓ Initialized gateway with provider: {gateway.provider.name}\n")
    
    # Test 1: Job Extraction
    print("Test 1: Job Extraction")
    job = await gateway.generate_structured(
        prompt="Extract job details from this senior data engineer posting",
        schema=ExtractedJob,
        agent_type="extraction_agent"
    )
    print(f"  Company: {job.company}")
    print(f"  Title: {job.title}")
    print(f"  Skills: {', '.join(job.required_skills[:3])}")
    print(f"✓ Job extraction works\n")
    
    # Test 2: Job Classification
    print("Test 2: Job Classification")
    classification = await gateway.generate_structured(
        prompt="Classify this data engineering role with Python and Spark",
        schema=JobClassification,
        agent_type="classification_agent"
    )
    print(f"  Category: {classification.primary_category}")
    print(f"  Confidence: {classification.confidence}")
    print(f"✓ Classification works\n")
    
    # Test 3: Match Scoring
    print("Test 3: Match Scoring")
    match = await gateway.generate_structured(
        prompt="Score candidate match for this position",
        schema=MatchScore,
        agent_type="matching_agent"
    )
    print(f"  Overall Score: {match.overall_score}/100")
    print(f"  Technical Skills: {match.dimension_scores['technical_skills']}")
    print(f"  Recommendation: {match.recommended_action}")
    print(f"✓ Match scoring works\n")
    
    # Test 4: Text Generation
    print("Test 4: Text Generation")
    text = await gateway.generate_text(
        prompt="Explain what a data engineer does",
        agent_type="helper"
    )
    print(f"  Response: {text}")
    print(f"✓ Text generation works\n")
    
    print("=== All Tests Passed ===")
    return True


if __name__ == "__main__":
    try:
        result = asyncio.run(test_gateway())
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
