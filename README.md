# Job Application Automation Platform

AI-powered job discovery, customization, application, and tracking system.

## Quick Start

```bash
# Setup
make setup

# Start services
make start

# Access
# Web:      http://localhost:3000
# API Docs: http://localhost:8000/docs
# Mock ATS: http://localhost:8080
```

## Architecture

- Backend: FastAPI + PostgreSQL + SQLAlchemy
- Frontend: Next.js 14 + TypeScript + Tailwind
- AI: Provider-agnostic gateway (mock/Anthropic/OpenAI)
- Browser: Playwright automation with checkpoints
- Storage: MinIO (S3-compatible)

## Project Structure

```
backend/          - FastAPI backend
apps/web/         - Next.js frontend  
apps/browser-worker/ - Playwright automation
fixtures/ats-sites/  - Mock ATS for testing
```

## Features Implemented (Phase 1)

✓ User authentication (JWT)
✓ Profile management
✓ Resume upload and parsing
✓ Job URL import
✓ AI extraction (mock mode)
✓ Job classification and scoring
✓ Resume tailoring with provenance
✓ Application preparation
✓ Browser automation (assisted mode)
✓ Mock ATS site
✓ Audit trail
✓ Docker Compose setup

## Commands

```bash
make start     - Start all services
make stop      - Stop services
make logs      - View logs
make migrate   - Run database migrations
make test      - Run tests
make clean     - Remove containers/volumes
```

## Testing the Vertical Slice

1. Register at http://localhost:3000/register
2. Create your profile
3. Upload a resume (PDF)
4. Import job from http://localhost:8080
5. Review match score
6. Prepare application
7. Review and approve
8. Browser fills form and pauses before submit

## Environment Variables

Backend (.env):
- DATABASE_URL
- JWT_SECRET
- AI_PROVIDER (mock/anthropic/openai)

Frontend (.env.local):
- NEXT_PUBLIC_API_URL
- NEXTAUTH_SECRET

## Documentation

See docs/ for detailed guides on:
- Architecture decisions
- Database schema
- API endpoints
- AI gateway usage
- Adding ATS adapters
- Security model

