# Architecture Overview

## System Design

```
┌─────────────────────────────────────────────────────────────┐
│                        User Browser                          │
└─────────────────┬───────────────────────────────────────────┘
                  │ HTTP/HTTPS
┌─────────────────▼───────────────────────────────────────────┐
│                    Next.js Frontend                          │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐   │
│  │Dashboard │ Profile  │ Resumes  │  Jobs    │   Apps   │   │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘   │
└─────────────────┬───────────────────────────────────────────┘
                  │ REST API
┌─────────────────▼───────────────────────────────────────────┐
│                    FastAPI Backend                           │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐   │
│  │   Auth   │ Profile  │ Resumes  │  Jobs    │   Apps   │   │
│  │  Routes  │  Routes  │  Routes  │  Routes  │  Routes  │   │
│  └─────┬────┴─────┬────┴─────┬────┴─────┬────┴─────┬────┘   │
│        │          │          │          │          │        │
│  ┌─────▼──────────▼──────────▼──────────▼──────────▼────┐   │
│  │              Services Layer                           │   │
│  │  • ProfileService  • ResumeService  • JobService     │   │
│  │  • ApplicationService  • WorkflowService             │   │
│  └─────┬────────────────────────────────────────────────┘   │
│        │                                                     │
│  ┌─────▼──────────────────────────────────────────────┐     │
│  │              AI Gateway                            │     │
│  │  ┌──────────┬──────────┬──────────┬──────────┐    │     │
│  │  │   Mock   │Anthropic │  OpenAI  │  Future  │    │     │
│  │  │ Provider │ Provider │ Provider │ Providers│    │     │
│  │  └──────────┴──────────┴──────────┴──────────┘    │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Agent System                             │  │
│  │  • ExtractionAgent   • ClassificationAgent           │  │
│  │  • MatchingAgent     • ResumeSelectionAgent          │  │
│  │  • TailoringAgent    • ReviewAgent                   │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────┬───────────────────────────────────────────────────┘
          │
          │ SQL
┌─────────▼─────────────────────────────────┬─────────────────┐
│         PostgreSQL                        │      Redis      │
│  • users          • applications          │  • Cache        │
│  • profiles       • workflows             │  • Locks        │
│  • resumes        • audit_events          │  • Sessions     │
│  • jobs           • model_calls           │                 │
└───────────────────────────────────────────┴─────────────────┘

┌───────────────────────────────────────────────────────────────┐
│                    Browser Worker (Playwright)                 │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │              Adapter System                              │ │
│  │  ┌──────────┬──────────┬──────────┬──────────────────┐  │ │
│  │  │   Mock   │ Generic  │   Real   │     Future       │  │ │
│  │  │   ATS    │ Adapter  │   ATS    │   Greenhouse,    │  │ │
│  │  │ Adapter  │          │ Adapters │   Lever, Ashby   │  │ │
│  │  └──────────┴──────────┴──────────┴──────────────────┘  │ │
│  └──────────────────────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Services: FormInspector, FieldMapper, CheckpointMgr   │ │
│  └──────────────────────────────────────────────────────────┘ │
└─────────────────────────┬─────────────────────────────────────┘
                          │ HTTP
┌─────────────────────────▼─────────────────────────────────────┐
│                    Target ATS Sites                            │
│     Mock ATS  |  Greenhouse  |  Lever  |  Ashby  |  Others    │
└────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│                    File Storage (MinIO)                        │
│  • Resume PDFs     • Screenshots     • Documents              │
└───────────────────────────────────────────────────────────────┘
```

## Data Flow: Complete Vertical Slice

### 1. User Registration & Profile Creation
```
User → Frontend → POST /api/auth/register → Backend
                                          → Hash password
                                          → Create user record
                                          → Return JWT token

User → Frontend → POST /api/profile → Backend
                                    → Create profile
                                    → Store work history, skills
```

### 2. Resume Upload
```
User → Frontend → POST /api/resumes → Backend
                                    → Upload file to MinIO
                                    → Calculate hash
                                    → Parse PDF (mock parser)
                                    → Extract structured data
                                    → Create ResumeFamily + ResumeVersion
                                    → Status: needs_review
```

### 3. Job Import
```
User → Frontend → POST /api/jobs/import-url → Backend
                                            → Fetch URL
                                            → Create WorkflowTask
                                            → Queue for processing

Background Worker:
  → ExtractionAgent.extract(raw_html)
     → AI Gateway (Mock Provider)
     → Return ExtractedJob schema
  → ClassificationAgent.classify(job_data)
     → Return JobClassification
  → Save CanonicalJob
  → Status: scored

  → MatchingAgent.score(job, profile)
     → Calculate dimension scores
     → Return MatchScore with explanation
  → Update job.score
```

### 4. Application Preparation
```
User → Frontend → POST /api/applications → Backend
                                         → Create Application record
                                         → Create WorkflowTask

Background Worker:
  → ResumeSelectionAgent.select(job, resumes, profile)
     → Return selected_resume_id + rationale
  
  → TailoringAgent.tailor(job, resume, profile)
     → Generate requirement-evidence matrix
     → Reorder/rewrite bullets (preserve facts)
     → Return ResumeTailoring with provenance
  
  → QuestionAgent.answer(questions, profile)
     → Classify risk level
     → Generate answers from verified facts
     → Return answers with sources
  
  → ReviewAgent.review(application, resume, answers)
     → Independent verification
     → Check for contradictions
     → Check claim provenance
     → Return ReviewResult
  
  → Update Application status: awaiting_review
```

### 5. User Review & Approval
```
User → Frontend → GET /api/applications/{id}
                → Display:
                   • Resume diff viewer
                   • Generated answers
                   • Risk classifications
                   • Review findings
                
User approves → POST /api/applications/{id}/approve
             → Update status: approved
```

### 6. Browser Submission
```
User → Frontend → POST /api/applications/{id}/start-browser

Backend → Create WorkflowTask
       → Queue for browser-worker

Browser Worker:
  1. process_application(application_id)
  2. Get application data from API
  3. Launch Playwright browser
  4. Navigate to job URL
  5. Detect ATS type (check data-ats attribute)
  6. Select adapter (MockATSAdapter)
  7. inspect_form()
     → Extract all fields with labels
     → Detect required fields
     → Map to canonical names
  8. For each field:
     → Get answer from application data
     → fill_field(field, answer)
  9. upload_document(resume_file)
  10. Create checkpoint
  11. Pause (Assisted Mode)
      → Status: paused
      → Waiting for user confirmation

User reviews preview → POST /api/applications/{id}/resume
                    → Continue workflow

Browser Worker:
  12. Resume from checkpoint
  13. preview_submission()
  14. submit()
  15. detect_confirmation()
      → Look for success indicators
      → Extract application ID
  16. Take final screenshot
  17. Update Application status: confirmed
  18. Create AuditEvent
```

## State Transitions

### Job States
```
discovered
  ↓ (extraction starts)
extracting
  ↓ (data extracted, classified)
scored
  ↓ (user views)
saved / shortlisted
  ↓ (user decides to apply)
preparing
  ↓ (application generated)
ready_for_review
  ↓ (user approves)
approved
```

### Application Pipeline States
```
not_started
  ↓
draft
  ↓ (generation complete)
awaiting_review
  ↓ (user approves)
approved
  ↓ (browser starts)
browser_running
  ↓ (pause point)
paused
  ↓ (user confirms)
browser_running
  ↓ (submission complete)
submitted
  ↓ (confirmation detected)
confirmed
```

### Workflow States
```
pending → running → completed
             ↓
       waiting_user_input
             ↓ (user responds)
          running → completed

OR

pending → running → failed
                     ↓ (retryable)
                  pending (retry)
```

## Security Model

### Authentication Flow
1. User submits credentials
2. Backend validates with bcrypt
3. Generate JWT with user_id claim
4. Return token (expires in 24h)
5. Frontend stores in HTTP-only cookie
6. All API calls include Authorization header
7. Backend validates token on each request
8. Dependency injection provides current_user

### Authorization Rules
- Users can only access their own data
- All API routes check user_id from JWT
- Database queries filter by user_id
- File URLs are pre-signed (expire in 1 hour)

### Sensitive Data Handling
- Passwords hashed with bcrypt
- JWT secrets in environment variables
- Sensitive profile fields in separate table (future)
- AI calls redact SSN, passwords, etc.
- Browser screenshots redact sensitive fields
- Audit logs exclude full sensitive values

### Browser Security
- No CAPTCHA circumvention
- Pause on authentication required
- Restricted to approved domains
- No arbitrary code execution
- Screenshot retention configurable
- User can disable automation per site

## Scaling Strategy (Future)

### Phase 1 (Current)
- Single server
- Docker Compose
- Database-backed workflows
- Single background worker

### Phase 2
- Multiple API instances behind load balancer
- Separate worker pool
- Redis for distributed locks
- Shared MinIO instance

### Phase 3
- Temporal for workflow orchestration
- Separate browser worker pool
- Queue-based job distribution
- Horizontal scaling

### Phase 4
- Multi-region deployment
- Read replicas for database
- CDN for static assets
- Elasticsearch for search
- Message queue (RabbitMQ/Kafka)

## Technology Stack Justification

**FastAPI**: 
- Modern async Python framework
- Automatic OpenAPI docs
- Pydantic validation built-in
- High performance

**Next.js 14**:
- App Router with server components
- Built-in API routes
- TypeScript support
- Excellent developer experience

**PostgreSQL**:
- ACID compliance
- JSON support (JSONB)
- Full-text search
- pgvector for embeddings (future)
- Mature and reliable

**Playwright**:
- Cross-browser support
- Async API
- Built-in screenshots
- Network interception
- Better than Selenium for modern sites

**Docker Compose**:
- Local development parity with production
- Service isolation
- Easy dependency management
- One-command startup

**MinIO**:
- S3-compatible API
- Self-hosted
- No cloud vendor lock-in
- Easy migration to AWS S3

## Monitoring & Observability (Future)

- Structured JSON logs → Elasticsearch → Kibana
- Metrics → Prometheus → Grafana
- Traces → Jaeger/Zipkin
- Errors → Sentry
- Uptime → UptimeRobot

## Deployment Options

### Development (Current)
```bash
docker-compose up
```

### Production - Docker Compose
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Production - Kubernetes (Future)
```
- Deployment per service
- StatefulSet for PostgreSQL
- PersistentVolumes for data
- Ingress for routing
- HorizontalPodAutoscaler
```

