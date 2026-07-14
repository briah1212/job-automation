# AI Gateway

Provider-independent AI gateway with mock mode for job application automation.

## Quick Start

```python
from app.ai_gateway import AIGateway
from app.ai_gateway.schemas import ExtractedJob

# Initialize with mock provider (no API key needed)
gateway = AIGateway(provider="mock")

# Extract structured data
job = await gateway.generate_structured(
    prompt="Extract details from this job posting...",
    schema=ExtractedJob,
    agent_type="extraction_agent"
)
```

## Provider Configuration

### Environment Variables

```bash
# Set provider (mock, anthropic, openai)
export AI_PROVIDER=mock

# API keys for real providers
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
```

### Programmatic Configuration

```python
# Auto-detect from env
gateway = AIGateway()

# Explicit provider
gateway = AIGateway(provider="mock")
gateway = AIGateway(provider="anthropic")
gateway = AIGateway(provider="openai")

# Pass API key directly
gateway = AIGateway(provider="anthropic", api_key="sk-ant-...")
```

## Usage Examples

### Text Generation

```python
text = await gateway.generate_text(
    prompt="Explain what a data engineer does",
    model="default",
    temperature=0.7,
    max_tokens=1000,
    agent_type="helper"
)
```

### Structured Output

```python
from app.ai_gateway.schemas import JobClassification

classification = await gateway.generate_structured(
    prompt="Classify this job posting",
    schema=JobClassification,
    model="default",
    temperature=0.7,
    max_tokens=2000,
    agent_type="classification_agent"
)

print(f"Category: {classification.primary_category}")
print(f"Confidence: {classification.confidence}")
```

## Available Schemas

All schemas are validated Pydantic models:

- **ExtractedJob**: Job details extraction
- **JobClassification**: Job categorization
- **MatchScore**: Candidate-job matching
- **ResumeSelection**: Best resume selection
- **ResumeTailoring**: Resume customization
- **ReviewResult**: Application review

## Mock Provider Behavior

The mock provider returns deterministic responses based on prompt keywords:

- **Extract/Job**: Returns sample job data for "Senior Data Engineer" at "Acme Corp"
- **Classify**: Returns appropriate category based on keywords (ML, data, software)
- **Match/Score**: Returns score of 78 with dimension breakdowns
- **Select**: Returns first resume ID found in prompt
- **Tailor**: Returns structured resume with changelog
- **Review**: Returns pass with no findings

Perfect for development and testing without API costs.

## Provider Details

### Mock Provider

- No API key required
- Instant responses
- Deterministic output
- Free

### Anthropic Provider

- Models: `claude-3-5-sonnet`, `claude-3-haiku`
- Structured output via tool use
- Rate limit handling
- Cost tracking

### OpenAI Provider

- Models: `gpt-4`, `gpt-3.5-turbo`
- Structured output via JSON mode
- Rate limit handling
- Cost tracking

## Model Aliases

Use simple aliases instead of full model names:

- `"default"`: Best model for the provider
- `"fast"`: Fastest/cheapest model
- `"smart"`: Most capable model

```python
# Use fast model
result = await gateway.generate_structured(
    prompt="...",
    schema=ExtractedJob,
    model="fast"
)
```

## Cost Tracking

All AI calls are automatically tracked in the database:

```python
# Get usage stats
stats = await gateway.get_usage_stats(
    user_id="user-123",
    agent_type="extraction_agent"
)

print(f"Total calls: {stats['call_count']}")
print(f"Total cost: ${stats['total_cost_usd']:.2f}")

# Get breakdown by agent type
by_agent = await gateway.get_usage_by_agent(user_id="user-123")
for agent in by_agent:
    print(f"{agent['agent_type']}: ${agent['total_cost_usd']:.4f}")
```

## Switching Providers

Change providers at runtime or via environment:

```python
# Development with mock
dev_gateway = AIGateway(provider="mock")

# Production with Anthropic
prod_gateway = AIGateway(provider="anthropic")

# Or set AI_PROVIDER env var
gateway = AIGateway()  # Auto-detects from env
```

## Error Handling

```python
try:
    result = await gateway.generate_structured(
        prompt="Extract job details",
        schema=ExtractedJob,
        agent_type="extraction_agent"
    )
except Exception as e:
    logger.error(f"AI generation failed: {e}")
    # Handle error
```

Rate limits and API errors are logged and re-raised.

## Testing

```bash
# Run tests (uses mock provider)
pytest app/ai_gateway/test_gateway.py

# Run with coverage
pytest app/ai_gateway/test_gateway.py --cov=app.ai_gateway
```

## Database Migration

```bash
# Apply migration to create model_calls table
alembic upgrade head
```

## Security

- API keys are never logged
- Sensitive fields (email, phone, etc.) are redacted from logs
- All responses include trace IDs for debugging
- Cost tracking prevents runaway usage

## Integration with Agents

```python
from app.ai_gateway import AIGateway
from sqlalchemy.ext.asyncio import AsyncSession

async def extraction_agent(job_text: str, db: AsyncSession):
    gateway = AIGateway(db_session=db)
    
    result = await gateway.generate_structured(
        prompt=f"Extract structured data from: {job_text}",
        schema=ExtractedJob,
        agent_type="extraction_agent",
        user_id=current_user.id
    )
    
    return result
```

## Files Created

```
backend/app/ai_gateway/
├── __init__.py              # Gateway exports
├── gateway.py               # Main AIGateway class
├── schemas.py               # Pydantic schemas
├── cost_tracker.py          # Usage tracking
├── providers/
│   ├── __init__.py
│   ├── base.py              # Provider base class
│   ├── mock_provider.py     # Mock implementation
│   ├── anthropic_provider.py # Anthropic Claude
│   └── openai_provider.py   # OpenAI GPT
├── test_gateway.py          # Tests
├── example_usage.py         # Usage examples
└── requirements.txt         # Dependencies

backend/app/models/
└── model_call.py            # Database model

backend/migrations/versions/
└── 002_add_model_calls.py   # DB migration
```
