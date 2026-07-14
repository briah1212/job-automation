"""
Example usage of the AI Gateway
"""
import asyncio
from app.ai_gateway import AIGateway
from app.ai_gateway.schemas import ExtractedJob, JobClassification, MatchScore


async def main():
    # Initialize with mock provider (no API key needed)
    gateway = AIGateway(provider="mock")
    
    print("=== Text Generation ===")
    text = await gateway.generate_text(
        prompt="Explain what a data engineer does",
        agent_type="example"
    )
    print(f"Response: {text}\n")
    
    print("=== Job Extraction ===")
    job = await gateway.generate_structured(
        prompt="Extract job details from this senior data engineer posting",
        schema=ExtractedJob,
        agent_type="extraction_agent"
    )
    print(f"Company: {job.company}")
    print(f"Title: {job.title}")
    print(f"Skills: {', '.join(job.required_skills[:3])}")
    print(f"Salary: ${job.salary_min:,} - ${job.salary_max:,}\n")
    
    print("=== Job Classification ===")
    classification = await gateway.generate_structured(
        prompt="Classify this data engineering role with Python and Spark",
        schema=JobClassification,
        agent_type="classification_agent"
    )
    print(f"Category: {classification.primary_category}")
    print(f"Confidence: {classification.confidence}")
    print(f"Explanation: {classification.explanation}\n")
    
    print("=== Match Scoring ===")
    match = await gateway.generate_structured(
        prompt="Score candidate match for this position",
        schema=MatchScore,
        agent_type="matching_agent"
    )
    print(f"Overall Score: {match.overall_score}/100")
    print(f"Dimension Scores: {match.dimension_scores}")
    print(f"Recommendation: {match.recommended_action}\n")
    
    print("=== Usage Stats ===")
    stats = await gateway.get_usage_stats()
    print(f"Stats: {stats}")


async def switch_providers():
    """Example of switching providers"""
    
    # Use mock provider (default)
    mock_gateway = AIGateway(provider="mock")
    print(f"Using provider: {mock_gateway.provider.name}")
    
    # Use Anthropic (requires ANTHROPIC_API_KEY env var)
    # anthropic_gateway = AIGateway(provider="anthropic")
    # or pass API key directly:
    # anthropic_gateway = AIGateway(provider="anthropic", api_key="sk-...")
    
    # Use OpenAI (requires OPENAI_API_KEY env var)
    # openai_gateway = AIGateway(provider="openai")
    
    # Auto-detect from AI_PROVIDER env var
    # gateway = AIGateway()  # reads from env


if __name__ == "__main__":
    asyncio.run(main())
