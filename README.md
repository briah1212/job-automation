# Job Application Automation Platform

AI-powered job discovery, customization, application, and tracking system.

## Quick Start

```bash
./setup-portable.sh
```

Fully self-contained: generates random secrets into `.env` on first run,
builds every image, and starts the whole stack (Postgres, Redis, MinIO, API,
job-worker, browser-worker, web, mock ATS). No external accounts or services
required - AI extraction defaults to `mock` mode.

```
Web:      http://localhost:3002
API Docs: http://localhost:8001/docs
Mock ATS: http://localhost:8080
```

Deploying to a remote server instead of your own machine? See
[QUICKSTART.md](./QUICKSTART.md) - pass the server's address so the frontend
is built pointing at it: `./setup-portable.sh your.server.address`.

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

1. Register at http://localhost:3002/auth/register
2. Create your profile
3. Upload a resume (PDF)
4. Import job from http://localhost:8080
5. Review match score
6. Prepare application
7. Review and approve
8. Browser fills form and pauses before submit

## Environment Variables

All configuration lives in one root `.env` file (see `.env.example`) that
`docker-compose.yml` reads for every service - there's nothing to configure
per-service. Key variables:

- `PUBLIC_HOST` - the address a browser will reach this deployment at (must
  be set correctly *before* building the `web` image - see QUICKSTART.md)
- `SECRET_KEY`, `CREDENTIAL_ENCRYPTION_KEY`, `INTERNAL_API_KEY`,
  `NEXTAUTH_SECRET` - generated automatically by `./setup-portable.sh`
- `AI_PROVIDER` (mock/anthropic/openai) - `mock` needs no API key

## Documentation

Integrating with a persistent remote browser (Hermes)? See [HERMES.md](./HERMES.md).

See docs/ for detailed guides on:
- Architecture decisions
- Database schema
- API endpoints
- AI gateway usage
- Adding ATS adapters
- Security model

