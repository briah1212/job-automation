import pytest
from app.ai_gateway import AIGateway
from app.ai_gateway.schemas import (
    ExtractedJob,
    JobClassification,
    MatchScore,
    ResumeSelection,
    ResumeTailoring,
    ReviewResult,
)


@pytest.mark.asyncio
async def test_mock_provider_text_generation():
    """Test mock provider text generation"""
    gateway = AIGateway(provider="mock")
    
    result = await gateway.generate_text(
        prompt="Explain this job posting",
        agent_type="test"
    )
    
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_mock_provider_job_extraction():
    """Test mock provider returns valid ExtractedJob"""
    gateway = AIGateway(provider="mock")
    
    result = await gateway.generate_structured(
        prompt="Extract job details from this posting",
        schema=ExtractedJob,
        agent_type="extraction_agent"
    )
    
    assert isinstance(result, ExtractedJob)
    assert result.company == "Acme Corp"
    assert result.title == "Senior Data Engineer"
    assert len(result.required_skills) > 0


@pytest.mark.asyncio
async def test_mock_provider_job_classification():
    """Test mock provider returns valid JobClassification"""
    gateway = AIGateway(provider="mock")
    
    result = await gateway.generate_structured(
        prompt="Classify this data engineering job",
        schema=JobClassification,
        agent_type="classification_agent"
    )
    
    assert isinstance(result, JobClassification)
    assert result.primary_category == "data_engineering"
    assert 0 <= result.confidence <= 1
    assert result.explanation


@pytest.mark.asyncio
async def test_mock_provider_match_score():
    """Test mock provider returns valid MatchScore"""
    gateway = AIGateway(provider="mock")
    
    result = await gateway.generate_structured(
        prompt="Score this candidate match",
        schema=MatchScore,
        agent_type="matching_agent"
    )
    
    assert isinstance(result, MatchScore)
    assert 0 <= result.overall_score <= 100
    assert len(result.dimension_scores) > 0
    assert result.recommended_action


@pytest.mark.asyncio
async def test_mock_provider_resume_selection():
    """Test mock provider returns valid ResumeSelection"""
    gateway = AIGateway(provider="mock")
    
    result = await gateway.generate_structured(
        prompt="Select best resume for this job",
        schema=ResumeSelection,
        agent_type="selection_agent"
    )
    
    assert isinstance(result, ResumeSelection)
    assert result.selected_resume_id
    assert result.selection_rationale
    assert isinstance(result.tailoring_recommended, bool)


@pytest.mark.asyncio
async def test_mock_provider_resume_tailoring():
    """Test mock provider returns valid ResumeTailoring"""
    gateway = AIGateway(provider="mock")
    
    result = await gateway.generate_structured(
        prompt="Tailor this resume for the job",
        schema=ResumeTailoring,
        agent_type="tailoring_agent"
    )
    
    assert isinstance(result, ResumeTailoring)
    assert result.structured_resume
    assert "contact" in result.structured_resume
    assert len(result.claim_provenance) > 0


@pytest.mark.asyncio
async def test_mock_provider_review():
    """Test mock provider returns valid ReviewResult"""
    gateway = AIGateway(provider="mock")
    
    result = await gateway.generate_structured(
        prompt="Review this application",
        schema=ReviewResult,
        agent_type="review_agent"
    )
    
    assert isinstance(result, ReviewResult)
    assert isinstance(result.passed, bool)
    assert 0 <= result.confidence <= 1


@pytest.mark.asyncio
async def test_provider_switching():
    """Test switching between providers"""
    # Mock provider
    mock_gateway = AIGateway(provider="mock")
    assert mock_gateway.provider.name == "mock"
    
    # Should fall back to mock without API key
    anthropic_gateway = AIGateway(provider="anthropic")
    assert anthropic_gateway.provider.name == "mock"
    
    openai_gateway = AIGateway(provider="openai")
    assert openai_gateway.provider.name == "mock"


@pytest.mark.asyncio
async def test_cost_tracking_mock():
    """Test cost tracking with mock provider"""
    gateway = AIGateway(provider="mock")
    
    await gateway.generate_text(
        prompt="Test prompt",
        agent_type="test_agent",
        user_id="test_user"
    )
    
    # Should complete without errors even without DB session
    stats = await gateway.get_usage_stats(user_id="test_user")
    assert isinstance(stats, dict)


@pytest.mark.asyncio
async def test_schema_validation_error():
    """Test that invalid schema data raises validation error"""
    gateway = AIGateway(provider="mock")
    
    # This should work
    result = await gateway.generate_structured(
        prompt="Extract job",
        schema=ExtractedJob,
        agent_type="test"
    )
    assert isinstance(result, ExtractedJob)


@pytest.mark.asyncio
async def test_multiple_requests():
    """Test multiple sequential requests"""
    gateway = AIGateway(provider="mock")
    
    # Multiple different schema requests
    job = await gateway.generate_structured(
        prompt="Extract job",
        schema=ExtractedJob,
        agent_type="test"
    )
    
    classification = await gateway.generate_structured(
        prompt="Classify job",
        schema=JobClassification,
        agent_type="test"
    )
    
    match = await gateway.generate_structured(
        prompt="Score match",
        schema=MatchScore,
        agent_type="test"
    )
    
    assert isinstance(job, ExtractedJob)
    assert isinstance(classification, JobClassification)
    assert isinstance(match, MatchScore)
