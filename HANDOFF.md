# Handoff Document

This document exists so that anyone, human or AI agent, can pick up this project without needing access to any server, prior chat history, or tribal knowledge.
It was requested at the end of a previous AI coding session but was never actually written until now.
Read this first, then follow the pointers at the bottom for deeper detail.

## Product Overview

`job-automation` is a single-user AI-powered platform for job discovery, resume customization, application submission, and application tracking.
The full product specification lives in `spec.md` at the repo root.

Core principles, per the spec, that any future work must respect:

- Truthfulness: never fabricate resume facts.
- Human-in-the-loop control: the system supports Manual, Assisted, and Trusted-Autopilot modes.
  Assisted is the default mode.
  Autopilot must stay off by default.
- No CAPTCHA or anti-bot circumvention of any kind.
- Quality over volume in job matching and applications.
- Explainability: matching and tailoring decisions should be traceable and understandable, not a black box.
- Idempotency: operations should be safe to retry without duplicating side effects.

## Architecture and Tech Stack

**Backend**: Python 3.9, FastAPI, SQLAlchemy, Alembic, Pydantic v2.
JWT authentication is implemented with direct calls to the `bcrypt` library rather than through `passlib`, because `passlib`'s `CryptContext` had compatibility problems with newer bcrypt releases (see Known Issues below).

**Frontend**: Next.js 14 using the App Router, TypeScript, Tailwind CSS, shadcn/ui components, and NextAuth.js for session handling.

**Database**: PostgreSQL 15, using UUID primary keys and a mix of JSONB and native Postgres `ARRAY` columns.

**Cache**: Redis 7.

**Object storage**: MinIO, an S3-compatible store.

**Browser automation**: Playwright (Python), driven through an ATS-adapter abstraction.
There is a base adapter interface, a working mock-ATS adapter, and a generic stub adapter intended as the starting point for future Greenhouse, Lever, Ashby, and Workday adapters.

**AI layer**: a provider-agnostic "AI Gateway" that supports `mock`, `anthropic`, and `openai` backends, selected via the `AI_PROVIDER` environment variable.
`mock` is the default and is the only provider that has actually been exercised so far.
No real LLM calls have been verified end-to-end yet.

**Workflow orchestration**: a DB-backed `workflow_tasks` table currently stands in for Temporal, which is what the spec originally recommended.
This was deliberately designed so that a future migration to real Temporal would not require rewriting business logic, only the orchestration layer around it.

## What's Done

### Phase 1 - Foundation and Minimal Vertical Slice

- Auth, profile CRUD, resume family/version models.
- Job import and normalization.
- Application records.
- The `workflow_tasks`, `audit_events`, and `model_calls` (AI cost tracking) tables.
- A Next.js frontend scaffold covering dashboard, auth, profile, resumes, jobs, and applications pages.
- A Playwright browser-worker with a mock-ATS adapter and checkpoint/resume support, plus a 3-page mock ATS fixture site used for testing.
- The backend was verified end-to-end via `curl` during that session.
- The frontend was built but was not actually deployed or verified until the current session (see the placeholder status section below for this session's findings).

### Phase 2 - Matching and Resume Selection

- `SearchProfile` model: career categories, include/exclude titles and skills, locations, remote policy, minimum salary, employment types, seniority levels, and target/excluded companies.
- `JobMatchScore` model: an overall score plus per-dimension scores (0-100 integers), hard blockers, strong matches, soft gaps, missing info, a recommended action, and a human-readable explanation.
- `MatchingAgent`: a weighted scorer using skill match (35%), experience (25%), seniority (15%), location (15%), and salary (10%), plus separate hard-blocker checks that can override the weighted score.
- `ResumeSelectionAgent`: scores candidate resume versions using coverage (40%), relevance (30%), recency (20%), and historical performance (10%).
- New API routes: full CRUD for search profiles, plus job match and select-resume endpoints.
- New frontend: search-profiles pages, an enhanced job inbox with filtering, and `MatchAnalysis` and `ResumeRecommendation` components.
- 18/18 backend tests passing, and a full API integration test passing.
- Committed as `335bb18` and pushed to GitHub.

### Phase 3 - Tailoring and Review (complete, 2026-07-17)

- Data model: `ProfileFact` (granular, provenance-tracked facts extracted from resumes/profile), `ResumeClaim`/`ResumeClaimSource` (per-bullet provenance linking generated resume text back to facts), `DocumentRendering`/`DocumentLock` (rendered PDF artifacts and user-lockable fields), `ApplicationQuestion`/`ApplicationAnswer`/`ApplicationAnswerSource` (normalized Q&A, replacing the old JSONB blob), `ReusableAnswer` (approved-answer knowledge base), `ApplicationReview` (automated review results).
- `ResumeTailoringAgent`: builds a requirement-evidence matrix (job requirements matched against verified profile facts, with strength scores and fact text shown), calls the AI gateway to draft a tailored resume variant, enforces user-set locks (exact title/dates/protected accomplishments) by reverting any locked field the AI tries to change, and records per-claim provenance.
- Resume rendering (PDF via reportlab), a diff viewer (added/removed/reordered content, keyword and summary changes, warnings), and field locks - all exposed via `POST /api/resumes/{id}/tailor`, `POST /api/resumes/{id}/render`, `GET /api/resumes/{id}/diff`, `POST/GET /api/resumes/families/{id}/locks`.
- `ApplicationQuestionAgent`: implements the spec's strict answer precedence (exact/canonical reusable answer -> deterministic calculation -> AI-generated from verified facts only -> require user input), a deterministic years-of-experience calculator (never guesses if dates can't be parsed), and hard-blocks guessing on high-risk questions (work authorization, sponsorship, etc.).
- `ApplicationReviewAgent`: an 18-point-style checklist (missing resume, unanswered high-risk questions, placeholder text, malformed dates, duplicate applications, wrong-company heuristics) plus one AI call using a deliberately separate prompt from the tailoring agent, per the spec's independence requirement.
- Frontend: real resume detail page (requirement-evidence matrix, diff viewer, lock management), real application review workspace (question generation, inline answer editing with source labels, review findings with pass/fail and confidence), and the resumes/applications list pages now show real data instead of Phase 1's hardcoded mocks.
- Also fixed while verifying this phase: the entire browser-based auth flow was non-functional (wrong login request shape/target, missing CORS origin, no JWT ever attached to API calls, no dashboard route guard, no `SessionProvider`) - all repaired and verified via both curl and a real browser walkthrough.

### Job Extraction Worker and Cover Letter Generation (complete, 2026-07-17)

Built at the user's direction, ahead of the spec's own phase order, because several Phase 3 features had nothing real to operate on without them:

- **Job extraction worker**: a new standalone process (`backend/worker.py`, run as its own `job-worker` Docker service, not gated behind a profile - it starts automatically with `docker compose up -d`) polls the `workflow_tasks` table for pending `job_extraction` tasks. `POST /api/jobs/import-url` now creates one of these tasks instead of leaving the job stuck in `extracting` forever. The worker fetches the job URL's raw HTML, strips it to plain text, runs a new `ExtractionAgent` (populates company/title/location/salary/skills/requirements) and a new `ClassificationAgent` (assigns a career category), and writes the result into `CanonicalJob.extracted_data` using the exact keys (`skills`, `category`, `seniority_level`, `requirements`) that `MatchingAgent` and `ResumeSelectionAgent` were already reading but never actually receiving real data for. Seniority is inferred heuristically in Python (title keywords, falling back to years-of-experience bands) rather than via an AI call, to keep this workstream independent of the AI gateway schema files. Verified end-to-end live: importing the mock-ats URL produces a fully populated, realistic `extracted_data` within seconds.
- Fixed a latent bug found while building this: `WorkflowTask`'s response schema declared a field named `metadata`, but the model column is `task_metadata` - same class of name-mismatch bug documented elsewhere in this file. Fixed to match.
- **Cover letter generation**: new `CoverLetter` model/table, `CoverLetterAgent` (same truthfulness discipline as the resume tailoring agent - only verified facts, must reference the specific role and company, avoid generic enthusiasm, connect 2-3 real experiences to the job's stated needs, respect tone and word-limit preferences), and three endpoints (`POST/GET/PATCH /api/applications/{id}/cover-letter`). Every generated letter starts as `needs_review`; saving an edit through the UI marks it `approved` (this is the review gate - there's no separate reusable-approval-policy system, kept intentionally simple per the user's request not to over-build this). Frontend: a self-contained `CoverLetterCard` component on the application review workspace with a tone selector, word-limit input, generate/regenerate, live word count, and an editable, savable textarea.
- Resume selection/tailoring itself needed no code changes - `ResumeSelectionAgent` already selected resumes by matching `ResumeFamily.target_category` against `job.extracted_data["category"]`, and `ResumeTailoringAgent`'s prompt already framed its job as reordering/emphasizing existing verified content rather than generating from scratch. Both were sitting unexercised for lack of real extracted job data - the worker above is what makes them actually useful now.

## What's Next

The following phases are defined in `spec.md` section 27 but have not been started.
Consult that section for full detail before starting any of them.

- **Phase 4 - Browser-Assisted Applications**: a real generic ATS adapter that goes beyond the mock, field mapping and learning, resume upload through the browser, a manual takeover UI, submission preview, and confirmation capture.
  Note that some pieces (checkpoints, the mock adapter) already exist from Phase 1's vertical slice.
  Phase 4's job is to generalize that beyond the mock site.
- **Phase 5**: real Greenhouse, Lever, and Ashby ATS adapters, with capability reporting and fallback behavior when a site isn't supported.
- **Phase 6 - Discovery Automation**: scheduled search profiles, company watchlists, public ATS ingestion, change detection, and notifications.
- **Phase 7 - Tracking and Analytics**: a Kanban-style tracker, timeline view, follow-up reminders, email integration, outcome tracking, analytics, and search-strategy recommendations.
- **Phase 8 - Controlled Autopilot**: an automation policy engine, trusted-domain rules, daily limits, submission locks, a kill switch, and full audit enforcement.
  The spec explicitly says this phase must stay off by default and should be built deliberately last, after everything above it is solid.

## Known Issues / Bugs Already Fixed

These have already been diagnosed and fixed once.
Read this before touching the related code so they don't get reintroduced.

1. **bcrypt/passlib incompatibility**: `passlib`'s `CryptContext` broke against newer bcrypt releases.
   Fixed by calling the `bcrypt` library directly in `backend/app/core/security.py` instead of going through `passlib`.
2. **SQLAlchemy reserved-keyword collision**: columns literally named `metadata` on the `Profile`, `WorkflowTask`, and `ModelCall` models collided with SQLAlchemy's declarative `Base`.
   Renamed to `profile_metadata`, `task_metadata`, and `call_metadata` respectively.
   Any schema or serialization code must match these exact names.
3. **Python 3.9 compatibility**: code originally used the `X | None` union syntax (PEP 604), which is not valid on Python 3.9.
   It was rewritten to `Optional[X]` throughout the backend and browser-worker.
   The original dev server ran Python 3.9, so this was a hard constraint at the time.
   If running locally on a newer Python version this is no longer a hard constraint, but the codebase currently still uses `Optional[X]` style throughout, and new code should match that style for consistency.
4. **SearchProfile/JobMatchScore three-way drift** between the SQLAlchemy models, the Pydantic schemas, and the actual Postgres columns.
   Examples: the model had `is_active` while the DB had `enabled`, the model had `desired_titles` while the DB had `include_titles`, and dimensional scores were modeled as `0.0`-`1.0` floats when the DB and spec use `0`-`100` integers.
   This was fixed by aligning the models and schemas to the actual DB columns, confirmed via `psql \d search_profiles`.
   This class of bug, model/schema/migration drift, has now bitten this project twice.
   It is worth adding a CI check or test that asserts model columns match the actual DB schema before it happens a third time.
5. **Invalid Next.js config**: `next.config.js` had `output: standalone` as a bare identifier instead of `output: 'standalone'` as a string.
   Fixed.
6. **FastAPI DELETE endpoint bug**: DELETE endpoints returning a 204 status cannot declare a `-> None` response body annotation.
   This annotation was removed from the search-profiles delete route.
7. **Deploy target had only Podman, not Docker**: the original deploy target ("bhead" / hostname `kn-head`) only had Podman available, which forced the use of `podman-compose` everywhere.
   This is not relevant now that development runs on Docker Desktop locally, but `setup-portable.sh` still auto-detects `docker compose`, `podman-compose`, or `docker-compose`, in that priority order, in case this ever needs to run on another Podman-only host again.
8. **Auth was completely non-functional through the browser** (found and fixed 2026-07-17, while verifying Phase 3): NextAuth's login call POSTed JSON to the wrong internal URL when the backend actually requires a form-urlencoded `OAuth2PasswordRequestForm`; CORS didn't allow the actual web port (3002); `api-client.ts` never attached a bearer token to any request; the dashboard had no route guard; and the app had no `SessionProvider` at all, which NextAuth's client-side session management needs to behave correctly. All fixed together - see commit `47a9125`.
9. **Automated review findings crashed the application review page permanently**: the backend wrapped each finding as `{"message": str}` to satisfy an overly-strict Pydantic schema, but the frontend (correctly) typed these as `string[]` and rendered them directly, throwing "Objects are not valid as a React child." Since the page auto-fetches the stored review on mount, this broke the page on every subsequent load, not just the button click. Fixed by making the schema `List[str]` end to end - see commit `193a995`.

## Known Remaining Gaps (not blocking, but worth knowing)

- The dashboard home page (`/dashboard`) still shows Phase 1's hardcoded mock stats and job cards - it was never wired to real data in any phase so far.
- There's no background worker to actually parse uploaded resumes or extract job postings - `parsed_data`/`extracted_data` stay empty after upload/import, so the tailoring pipeline has nothing real to work with until this exists. This blocks a fully realistic end-to-end walkthrough through the UI alone (verification required seeding `parsed_data` directly via SQL).
- No file-download/static-serving mechanism exists for rendered resume PDFs - `POST /api/resumes/{id}/render` writes a real file and returns its path, but there's no way to actually download it from the browser yet.
- No cover-letter generation exists - the review workspace shows a clearly-labeled placeholder instead.
- Minor: `GET /api/resumes/{id}` (singular, by id) doesn't exist on the backend - the resume detail page calls it once for family metadata and silently no-ops on the 404; harmless but should either get a real endpoint or have the dead call removed.
- Minor: blank high-risk answers awaiting user input are labeled "Your edit" in the question list, which reads as if the user already typed something - worth a distinct label for "needs your input" vs. "you edited this."
- Minor: the "View Resume" link on the application review page uses the resume's `family_id` instead of its `id`, so it currently links to a URL the resume detail page can't resolve.

## Current Local Environment Status (as of this handoff)

Verified locally on 2026-07-17, running on Docker Desktop (not the old remote server). All six services are up: `postgres`, `redis`, `minio`, `api`, `mock-ats`, and `web`.

- The API is confirmed healthy: `GET /health` returns 200, and `/docs` serves the Swagger UI correctly.
- The database was one migration behind (`002_add_model_calls` instead of head).
  It has been brought up to date; head is now `e9374f596c0a` (`add_search_profiles_and_matching`).
- `apps/web/.env.local`, `apps/web/.env.example`, and `README.md` had stale references to the API running on port 8000.
  These have been fixed to point to the correct port, 8001.
- The `web` frontend now builds and runs.
  Getting there required fixing several real bugs, not just the original lint errors:
  - `react/no-unescaped-entities` lint errors (raw apostrophes in JSX) in `app/auth/login/page.tsx` and `app/dashboard/applications/[id]/page.tsx`, fixed by escaping them.
  - A genuine data-model gap: `GET /api/resumes` only returns resume *families*, but the job-detail page needs resume *versions* to match against `selection.selected_resume_id` (which is a version id, confirmed via `ResumeSelectionAgent`). Added a new `GET /api/resumes/versions` endpoint and a matching `apiClient.getResumeVersions()` method, and pointed the job-detail page at it instead of silently type-casting the wrong shape.
  - Missing NextAuth type augmentation (`session.user.id` had no type), fixed by adding `apps/web/types/next-auth.d.ts`.
  - A missing `apps/web/public/` directory that the Dockerfile expects to copy.
  - `docker-compose.yml`'s `web` service bind-mounted `./apps/web:/app` over the built image, which overwrote the standalone-build `server.js` with raw source and crash-looped the container. Removed that bind mount and its companions (`/app/node_modules`, `/app/.next`) since the Dockerfile builds a self-contained production `standalone` bundle, not a dev server - live-reload was never wired up for this service, so there is currently no hot-reload frontend dev loop in Docker. To iterate on frontend code with hot reload, run `cd apps/web && npm install && npm run dev` directly on the host instead of through Compose, pointed at the dockerized API on port 8001; re-run `docker compose build web` only when you want to verify the production build.
  - Host port 3000 was already taken by an unrelated container from a different project (`media-converter-frontend-1`). Remapped `web` to host port **3002** instead of touching that container; `NEXTAUTH_URL` was updated to match.
- `browser-worker` was intentionally not started, since it's an on-demand job, not a persistent service.
  It has not been built on this machine yet.
- Running `./phase2_test.sh` against the live stack passed steps 1 through 6 (create user, update profile, create search profile, import job, calculate match score, retrieve match score) but failed at step 7, resume upload.
  The script expects a top-level `id` in the response, but the actual `/api/resumes` POST response returns a nested `{"family": {...}, "version": {...}}` shape, each with its own `id`.
  This looks like the API's resume-family/resume-version split shipped after the test script was last updated; the script itself is stale, not necessarily the API.
  The script is also not idempotent: rerunning it with the same hardcoded test email fails at step 1 since that user already exists.
  This script should be updated as part of Phase 3 work, since Phase 3 will add more resume/answer endpoints that deserve smoke-test coverage anyway.

## Local Setup Instructions

This all assumes Docker Desktop running locally, not the old remote dev server.

1. From the repo root, run `docker compose up -d`.
   This brings up `postgres`, `redis`, `minio`, `api`, `web`, and `mock-ats`.
2. `browser-worker` is defined as a Compose profile and is not started automatically.
   Start it on demand with `docker compose run --rm browser-worker ...`.
3. Service endpoints:
   - API: `http://localhost:8001` (not 8000; port 8000 was remapped to avoid a conflict left over from the old remote server context, kept as-is for consistency with existing docs and scripts).
   - Frontend: `http://localhost:3002` (not 3000; remapped to avoid a conflict with an unrelated container from another project on this machine - if that conflict doesn't exist on your machine, feel free to change it back to 3000 in `docker-compose.yml`).
   - Mock ATS: `http://localhost:8080`.
   - MinIO console: `http://localhost:9011`.
   - Postgres: `localhost:5432`.
   - Redis: `localhost:6379`.
4. `AI_PROVIDER=mock` is the default in `backend/.env`.
   Set it to `anthropic` or `openai` along with a real API key to exercise non-mock behavior; this path has not been tested yet.
5. Test credentials from prior E2E runs: `demo@test.com` / `demo123`.
   These are ephemeral, dev-only credentials, not a production account.
6. Run `./phase2_test.sh` for a smoke test of the combined Phase 1 + Phase 2 API flow.

## Deployment Notes

Previous work happened on a remote dev server reached via `ssh bhead` (hostname `kn-head`).
That was not this session's actual target and should not be treated as the deployment target going forward.

The real deployment target going forward is a VPS called "hermes."
This was not mentioned anywhere in `spec.md` or the prior session transcript, so no existing infrastructure or configuration in this repo assumes it.
Deployment tooling and any hermes-specific configuration still need to be created from scratch in a future phase.

## Where to Find Things

- `spec.md` - the full product specification, including the phase breakdown in section 27.
- `session_transcript.txt` - a detailed history of the Phase 1 and Phase 2 build session.
- `PHASE2_TEST_REPORT.txt` - detail on the Phase 2 test run referenced above.
