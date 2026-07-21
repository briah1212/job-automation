# Browser State Machine: Design Proposal

Status: architecture reviewed and approved 2026-07-20.
Open questions from the original draft are resolved in section 12; implementation proceeds per the build order in section 11.
Once the first vertical slice lands, the relevant sections should be folded into `spec.md` (proposed as new subsections 14.9-14.11) so the spec and the implementation don't drift apart, the same class of problem `HANDOFF.md` already flags twice for other subsystems.

## 1. Goal recap

Transform `BrowserWorker` from a single-purpose form filler into a state machine that can drive the full application lifecycle: landing page, apply button, login, account creation, profile setup, resume upload and parse-wait, the multi-page application itself, review, and submit-ready.
The deterministic DOM-based field-filling pipeline (`inspect_form` -> `FieldMapper` -> `fill_field` via Playwright) stays the primary execution path and is not being replaced.
The LLM's role stays exactly where it already is in the rest of the codebase: answering genuinely unknown questions under the existing truthfulness/no-guessing discipline, never deciding what to click or whether to submit.

## 2. How this maps onto `spec.md` section 14

Section 14 already specifies most of the shape of this system: the `AtsAdapter` protocol, DOM-first form inspection ("do not rely only on screenshots when DOM information is available"), field mapping with reviewable learned mappings, a dynamic-questions fallback pipeline, checkpoints, manual takeover, and confirmation detection.
What's missing from the spec, and what this document adds, is the actual state machine that sequences all of those pieces together, plus a piece the spec never designed at all: durable storage of credentials for ATS accounts the system creates on the user's behalf.

There is one direct conflict worth flagging before anything else. `spec.md` section "Example C: Unsupported Workday Flow" describes the intended behavior as: "The generic adapter can inspect the page but cannot safely complete account creation... the user takes over the browser... after login, the user returns control."
**Resolved 2026-07-20: automation always attempts account creation first.**
Manual intervention is reserved for cases where automation is genuinely blocked - CAPTCHA, MFA, email verification, an unsupported flow, or repeated failure - never simply because account creation is required.
`spec.md`'s Example C is superseded by this decision and should be rewritten once this lands (proposed replacement text is in section 8).

## 3. `BrowserState`

```python
class BrowserState(str, Enum):
    LANDING = "landing"
    APPLY = "apply"
    LOGIN = "login"
    CREATE_ACCOUNT = "create_account"
    EMAIL_VERIFICATION = "email_verification"
    PROFILE_SETUP = "profile_setup"
    RESUME_UPLOAD = "resume_upload"
    RESUME_PARSE_WAIT = "resume_parse_wait"
    APPLICATION = "application"
    REVIEW = "review"
    SUBMIT_READY = "submit_ready"
    SUBMITTED = "submitted"
    MANUAL_INTERVENTION = "manual_intervention"
    UNKNOWN = "unknown"
    FAILED = "failed"
```

This is your proposed enum plus two additions:

- `UNKNOWN`: returned when state detection can't confidently classify the page, instead of silently guessing.
  A run of consecutive `UNKNOWN` detections (see section 6) is what actually triggers `MANUAL_INTERVENTION`, rather than any single ambiguous page pausing the whole run.
- `FAILED`: a distinct terminal state from `MANUAL_INTERVENTION`.
  `MANUAL_INTERVENTION` means "a human needs to act, then automation resumes."
  `FAILED` means "retries are exhausted or the failure is unrecoverable," and maps to `WorkflowStatus.failed` the same way it already does today.

### Relationship to the state fields that already exist

`BrowserState` is a new, more granular field, not a replacement for the state tracking already built this session.
It's the missing middle layer:

| Layer | Field | Granularity |
|---|---|---|
| Outer workflow status | `WorkflowTask.status` (`WorkflowStatus`) | pending / running / waiting_user_input / completed / failed / cancelled |
| Pipeline status shown to the user | `Application.pipeline_status` | draft / browser_running / paused / submitted / confirmed / failed_retryable / ... |
| **New: browser state** | `WorkflowTask.task_metadata["browser_state"]` | the full `BrowserState` enum above |
| Human-readable current step | `WorkflowTask.current_step` | mirrors `browser_state.value`, already exists, already read by the API |

`MANUAL_INTERVENTION` and `EMAIL_VERIFICATION` both map to the existing `WorkflowStatus.waiting_user_input` / `ApplicationPipelineStatus.paused` outer states.
`browser_state` is what distinguishes "paused because a human needs to click approve on a filled form" (today's only pause reason) from "paused because a human needs to solve a CAPTCHA" or "paused because a human needs to check their email," which need different frontend treatment and different resume logic (section 7).

## 4. The control loop

```python
async def run_state_machine(self, page: Page, adapter: ATSAdapter, ctx: RunContext) -> dict:
    transitions = 0
    started_at = time.monotonic()

    while True:
        transitions += 1
        if transitions > MAX_TRANSITIONS or (time.monotonic() - started_at) > MAX_WALL_CLOCK_SECONDS:
            return await self._escalate(page, ctx, reason="state machine exceeded transition/time budget")

        state, confidence = await adapter.detect_state(page)
        await self.checkpoint_manager.create_checkpoint(session_id=ctx.session_id, page=page, step=state.value, ...)

        if state == BrowserState.UNKNOWN:
            ctx.unknown_streak += 1
            if ctx.unknown_streak >= MAX_UNKNOWN_STREAK:
                return await self._escalate(page, ctx, reason="could not classify page state")
            state = ctx.last_known_state  # retry the last confident handler rather than giving up immediately
        else:
            ctx.unknown_streak = 0
            ctx.last_known_state = state

        if state == BrowserState.SUBMIT_READY:
            return {"success": True, "state": state.value, "session_id": ctx.session_id}
        if state == BrowserState.MANUAL_INTERVENTION:
            return await self._pause_for_manual_intervention(page, ctx)

        result = await adapter.handle_state(state, page, ctx)
        if not result.success:
            return await self._escalate(page, ctx, reason=result.error)

        await self._wait_for_transition(page)
```

Key points, each one directly motivated by a bug found while verifying the current (much simpler) loop:

- **A hard transition/time budget is not optional.** The `navigate_next` bug found and fixed earlier this session caused exactly this failure mode (a "successful" click that made zero progress, retried forever) in a system with three states.
  A graph with thirteen states has more ways to loop or oscillate, not fewer.
  `MAX_TRANSITIONS` and `MAX_WALL_CLOCK_SECONDS` are circuit breakers, both configurable, both defaulting conservatively (proposed: 40 transitions, 15 minutes), and both routes to `_escalate`, never a silent retry-forever.
- **Every state transition creates a checkpoint before executing the handler**, not just at a few hardcoded points like today.
  This is what makes mid-flow resume (section 7) possible for arbitrary states, not just the one "ready to submit" pause the current code supports.
- **`_wait_for_transition` needs to handle both real navigation and SPA-style DOM mutation.** The mock ATS fixture already proved this matters: its three "pages" are `display:none` toggles on one URL, not real navigation.
  A real ATS (Workday in particular) is heavily client-side-rendered and will behave the same way.
  Proposed implementation: race `page.wait_for_load_state("networkidle")` against a short `MutationObserver`-based JS wait injected via `page.evaluate`, bounded by a timeout, falling through to state re-detection either way rather than trusting either signal alone.

## 5. `ATSAdapter` interface v2

```python
class ATSAdapter(ABC):
    # Existing primitives - unchanged, still the actual execution mechanism.
    async def inspect_form(self, page: Page) -> ApplicationForm: ...
    async def fill_field(self, page: Page, field: FormField, value: str) -> FillResult: ...
    async def upload_document(self, page: Page, field: FormField, file_path: str) -> UploadResult: ...
    async def navigate_next(self, page: Page) -> NavigationResult: ...
    async def submit(self, page: Page) -> SubmissionResult: ...
    async def detect_confirmation(self, page: Page) -> ConfirmationResult: ...
    def get_name(self) -> str: ...

    # New: state machine layer, built on top of the primitives above.
    async def detect_state(self, page: Page) -> tuple[BrowserState, float]: ...
    async def handle_state(self, state: BrowserState, page: Page, ctx: RunContext) -> StateHandlerResult: ...
```

`handle_state` dispatches internally to per-state handler methods (`handle_login`, `handle_account_creation`, `handle_profile_setup`, `handle_resume_upload`, `handle_application_page`, `handle_review`), which is your proposed shape; I've collapsed it to one abstract entry point plus concrete internal methods so `BrowserWorker`'s control loop doesn't need to know the full method-per-state list, only adapters do.
`handle_application_page` and `handle_review` are thin wrappers around the existing `inspect_form` / `FieldMapper` / `fill_field` / `navigate_next` pipeline - this is the piece explicitly not being replaced, just given a name in the new interface.

`GenericAdapter` gets real implementations of every new method for the first time (today it's mostly stubs - `navigate_next` unconditionally returns failure, there's no login/account-creation handling at all).
A future `WorkdayAdapter` overrides `detect_state` and the account-related handlers with tenant-aware logic; it can fall through to the generic form-filling handlers unchanged.

## 6. Robust state detection

Single-selector detection is exactly what broke twice this session (`navigate_next` grabbing the wrong DOM element, `submit`'s reset-to-page-1 problem).
A thirteen-state graph raises the cost of that failure mode, so detection should be signal-combination and confidence-scored from the start, not selector-first with signals bolted on later.

```python
async def detect_state(self, page: Page) -> tuple[BrowserState, float]:
    signals = Signals(
        url=page.url,
        headings=await self._get_headings(page),
        buttons=await self._get_button_texts(page),
        has_password_field=await self._has(page, 'input[type="password"]'),
        has_confirm_password_field=await self._has(page, '[name*="confirm" i][type="password"]'),
        has_file_input=await self._has(page, 'input[type="file"]'),
        visible_field_count=await self._count_visible_fields(page),
        aria_roles=await self._get_aria_roles(page),
    )
    scores = {state: rule.score(signals) for state, rule in self._rules.items()}
    best_state, best_score = max(scores.items(), key=lambda kv: kv[1])
    return (best_state, best_score) if best_score >= CONFIDENCE_THRESHOLD else (BrowserState.UNKNOWN, best_score)
```

Each rule combines multiple weighted signals rather than one selector - for example `LOGIN` scores highly on (password field present, no confirm-password field, URL contains `login`/`signin`, a button labeled "Sign in"/"Log in"), while `CREATE_ACCOUNT` scores highly on (password field *and* confirm-password field present, URL contains `signup`/`register`/`create-account`, a button labeled "Create account"/"Sign up").
`GenericAdapter` ships a baseline rule set covering the states in section 3 using only generic signals (no site-specific selectors); a platform-specific adapter can override individual rules with stronger, tenant-aware signals without touching the others.

## 7. Manual intervention: pause and resume

Two genuinely different resume strategies are needed, not one, because "resume" means something different depending on which state was paused in:

**Structural resume** (`LOGIN`, `CREATE_ACCOUNT`, `EMAIL_VERIFICATION`, `PROFILE_SETUP`): by the time a human finishes verifying an email or solving a CAPTCHA, the *site's own server-side state has changed* - the account now exists and is verified.
Replaying the pre-verification form data would be wrong; the correct resume action is closer to "load the login page fresh, authenticate with the now-valid stored credentials, and re-run `detect_state`" than to any kind of checkpoint replay.

**Replay resume** (`APPLICATION`, `REVIEW`): this is the pattern already built and verified this session for `ready_to_submit` -> `submit` (`BrowserWorker._replay_filled_fields`), generalized to resume into any page of a multi-page application, not only the last one.
Client-side multi-page forms reset to page 1 on reload (confirmed against the mock ATS fixture), so resuming here means replaying `checkpoint.filled_fields` page-by-page via the existing `inspect_form`/`fill_field`/`navigate_next` primitives up to the checkpointed page, exactly like the fix already shipped, just no longer special-cased to only the final page.

`BrowserState` is what selects which resume strategy runs; this is the main reason it needs to be persisted per-checkpoint, not just logged.

### Durability: checkpoints need to move out of the container

**Resolved 2026-07-20: Postgres for durable state and checkpoints, MinIO for files (screenshots, resumes, cover letters, generated documents).**
No container-local persistence except as a short-lived write buffer before the durable write completes.
The system must recover after a container restart or redeploy with no loss of in-flight session state.

Today, `CheckpointManager` writes to `/tmp/checkpoints/{session_id}/` inside the `browser-worker` container - not a mounted volume, so a container recreation (not just a restart) loses it entirely.
That was an acceptable gap for the current single pause point (assisted-mode approval, expected to resolve in seconds to minutes).
It stops being acceptable once pauses can mean "waiting for a human to check their email," which can reasonably take hours, during which a deploy, a crash, or `docker compose up --force-recreate` would silently destroy the only record that an account was already created for that tenant - risking a duplicate signup attempt against the real site.

`spec.md`'s own data model already anticipates this and was never actually followed: section 16 lists `browser_sessions` and `browser_checkpoints` as tables, but the implementation uses local JSON files instead.
`browser-worker` already writes directly to Postgres via SQLAlchemy for `WorkflowTask` (`queue_worker.py`, no HTTP indirection), and checkpoint data carries no secrets (already redacted before storage) - so checkpoints follow the same direct-write pattern, not a new internal API.
Screenshots go to MinIO (already provisioned, already used for resumes) via the same client the backend already uses.
Every state transition writes a checkpoint row before its handler runs (section 4), which is what makes "resume from the last completed state, not from scratch" possible after any crash or restart, not only at the few hardcoded points today's checkpointing covers.

### Orphan recovery

`HANDOFF.md` already documents (from this session) that a `browser-worker` crash mid-task orphans its `WorkflowTask` in `running` forever, since the poll loop only ever queries `status="pending"`.
That gap becomes materially worse here: a crash during `MANUAL_INTERVENTION` would strand a task that's waiting on a human indefinitely with no path back into the queue even after the human acts.

**Status: half-built as of Phase 1.** `queue_worker.py._reclaim_stale_tasks` exists and is verified working (it correctly detects and reclaims a stale `running` task back to `pending`), which closes the "orphaned forever" half of the problem.
It does not yet do the second half - resume from the last known `browser_state` - because that requires the state-machine dispatch this document is proposing, which doesn't exist until Phase 3.
Today a reclaimed task just restarts `process_application` from page 1, discarding whatever was already durably checkpointed.
That's harmless right now (no state has a real-world side effect yet) but must be fixed as part of Phase 3's control loop, before Phase 4's account auto-creation lands - a reclaim-triggered restart during account creation risks a duplicate signup attempt against the real ATS, exactly what this durability work exists to prevent.

## 8. Credential vault

**Resolved 2026-07-20: build this now**, encrypted with a key from `CREDENTIAL_ENCRYPTION_KEY`, behind an interface a real secret manager can implement later without touching any caller.

```python
class CredentialCipher(ABC):
    @abstractmethod
    def encrypt(self, plaintext: str) -> bytes: ...
    @abstractmethod
    def decrypt(self, ciphertext: bytes) -> str: ...

class FernetCredentialCipher(CredentialCipher):
    """Local/dev implementation: symmetric key from CREDENTIAL_ENCRYPTION_KEY."""

class VaultCredentialCipher(CredentialCipher):
    """Future: HashiCorp Vault / AWS Secrets Manager / GCP Secret Manager.
    Not implemented now - the interface exists so this can be dropped in later
    with a config flag, no changes to ats_credentials or the callers below."""
```

Only `FernetCredentialCipher` is built in this phase; `CredentialCipher` is the seam that keeps the door open, per instruction not to block on secret-manager integration.

New table, not currently in `spec.md`'s data model:

```
ats_credentials
  id                uuid pk
  user_id           uuid fk -> users
  ats_platform      varchar        -- "workday", "greenhouse", ...
  tenant_key        varchar        -- e.g. the *.myworkdayjobs.com subdomain
  email             varchar        -- the email used to create the account
  encrypted_password bytea         -- Fernet-encrypted, see below
  status            varchar        -- active | needs_verification | revoked | login_failed
  created_at, updated_at, last_used_at
  unique(user_id, ats_platform, tenant_key)
```

Design decisions, each with a reason:

- **Encryption key lives only in the backend service, never in `browser-worker`.** `browser-worker` is the process directly exposed to untrusted third-party page content (`spec.md` section 15.1's exact threat model - "treat all job pages as hostile input").
  It should not be the process holding a key that decrypts every stored ATS password.
  Proposed flow: `browser-worker` calls a new internal-only backend endpoint (`POST /api/internal/ats-credentials:get-or-create`) over the Docker network; the backend does the encrypt/decrypt and returns plaintext credentials only for that one call, for that one tenant.
  This also happens to be what the currently-unused `API_URL: http://api:8000` env var already sitting in `browser-worker`'s compose config was presumably meant for - nothing calls it today.
- **Encryption via `cryptography.fernet.Fernet`**, keyed by a new `CREDENTIAL_ENCRYPTION_KEY` secret, deliberately separate from `SECRET_KEY`/`JWT_SECRET`.
  Key separation means a JWT secret leak doesn't also compromise every stored third-party password.
  No encryption precedent exists anywhere in the codebase yet (checked); this would be new infrastructure, small in surface area but worth its own careful review given what it protects.
- **Tenant scoping via `tenant_key`**, not just `ats_platform`, because a Workday-hosted job at Company A and Company B are different tenants with different accounts, even though both are "Workday."
  Extraction strategy: parse the subdomain out of the application URL at detection time (e.g. `companyname` from `companyname.wd1.myworkdayjobs.com`).
- **Password generation**: a secrets-module-generated high-entropy password meeting whatever policy the create-account form's own client-side validation exposes (length/character-class requirements detected the same way form fields are - inspected, not assumed).
- **Reuse and staleness**: `get-or-create` returns the existing credential row if one exists for `(user, platform, tenant)`, tries it first, and if login fails marks the row `login_failed` and falls through to `MANUAL_INTERVENTION` (Example C's flow) rather than generating a second account, which would just create clutter and possible duplicate-application risk on the ATS side.

### Reconciling with `spec.md` Example C

Proposed final behavior, combining both: on reaching `CREATE_ACCOUNT`, check the vault first; if a working credential exists, skip straight to `LOGIN`.
If none exists, attempt automatic creation.
If that attempt hits a CAPTCHA, an unrecognized required field, or anything else automation isn't confident about, stop there and follow Example C exactly - pause, surface a "Complete account setup" task, let the human finish it, `structural resume` (section 7) once they hand control back.
Automatic creation is the fast path added on top of the existing safety net, not a replacement for it.

## 9. Dynamic questions bridge (not new work, just wiring)

`ApplicationQuestionAgent` already implements the exact precedence order `spec.md` section 14.4 wants for unknown fields (exact reusable answer -> hard-block on high-risk guessing -> deterministic calculation -> AI generation grounded in verified facts -> ask the user).
It already lives in `backend/app/agents` and is already used for pre-application Q&A.
It is not currently reachable from `browser-worker` at all - the container has no access to `app.agents` or the AI gateway, only to `app.models`/`app.core.database`.

Proposed wiring: when `FieldMapper` can't map a field and no reasonable default exists (the exact situation that silently skipped the consent checkbox and broke the real end-to-end test earlier this session), `browser-worker` calls a new internal backend endpoint (`POST /api/internal/answer-question`) with the field's label/type/options/page context, gets back the same shaped answer `ApplicationQuestionAgent.generate_answer` already returns, and either fills it (if `needs_user_input` is false) or transitions to `MANUAL_INTERVENTION` with the pending question attached (if true) - which is also, finally, the first real producer of the `paused_question` / `answer-pending-question` API flow that already exists in `browser_automation.py` but has never had anything upstream that could trigger it.
No new AI logic; this is entirely reuse of what's already built and audited, just connected to the browser loop for the first time.

## 10. What this document does not include

Per the explicit constraints given:

- No autonomous vision/screenshot-driven agent anywhere in this design.
  Screenshots stay checkpoint/audit artifacts, exactly as `spec.md` section 14.2 specifies ("do not rely only on screenshots when DOM information is available").
- No inbox automation for email verification.
  `EMAIL_VERIFICATION` is a `MANUAL_INTERVENTION` state, full stop, in this phase.
- No change to who authorizes final submission.
  `SUBMIT_READY` still requires the existing explicit `approve-submit` human action; `spec.md` section 15.1's "keep submission authorization outside the LLM" holds exactly as it does today, since nothing here gives the LLM (used only in section 9) any path to submission.

## 11. Build order (final)

1. **Durability layer - done, verified live 2026-07-20.** `browser_sessions`/`browser_checkpoints`/`ats_credentials` migration and models, `CheckpointManager` rewritten onto Postgres + MinIO, orphan-reclaim query.
   Independently reviewed afterward; six real findings fixed (form_state was reaching Postgres unredacted - now fixed; a missing `db.rollback()`; a `datetime.now()`/`utcnow()` inconsistency; dead code; an exception-path gap leaving `browser_session.status` stale; and a documented, deliberately-deferred limitation - reclaim resets `WorkflowTask.status` but not `task_metadata`, so a reclaimed task currently restarts from page 1 rather than resuming from its checkpoint. Harmless until Phase 4's account creation lands; must be fixed as part of item 3 below, not patched into code that item 3 replaces).
2. **Credential vault - done, verified live 2026-07-20.** `CredentialCipher`/`FernetCredentialCipher`, `ats_credentials` access via `app.services.ats_credential_vault`, and `POST /api/internal/ats-credentials/get-or-create` + `.../mark-status`, gated by a new `INTERNAL_API_KEY` header check (necessary because `api`'s port is published to the host, so Docker network isolation alone doesn't protect this route). Verified: encryption round-trips correctly, get-or-create is idempotent per (user, platform, tenant), the browser-worker-side HTTP client works end-to-end across the container network, and - the one that actually matters - `browser-worker`'s live environment was checked directly and confirmed to have no `CREDENTIAL_ENCRYPTION_KEY` at all.
3. **`BrowserState` + `ATSAdapter` v2 + the state-machine control loop - done, verified live 2026-07-20** in `BrowserWorker`, replacing `_fill_application`'s linear loop with `run()`/`resume()`/`run_state_machine()` (see `browser_worker/state.py`, `worker.py`).
   `handle_application_page`/`handle_review` wrap the existing `inspect_form`/`FieldMapper`/`fill_field` pipeline essentially unchanged - the "don't replace deterministic field mapping" constraint held.
   Every transition checkpoints before the handler runs. The orphan-reclaim TODO from item 1 is now closed for real: `resume()` with no checkpoint falls straight through to a fresh run, so `queue_worker.py` can always call `resume()` and get correct behavior whether the task is fresh, reclaimed, or post-approval.
   Verified live end to end: a full run through every state (`landing` -> `apply` -> `create_account` -> `profile_setup` -> `resume_upload` -> `resume_parse_wait` -> `application` (x2 pages) -> `review` -> `submit_ready` -> approve -> replay -> `submitted`, real confirmation ID captured), plus separately verified `email_verification` -> `manual_intervention` escalation, the missing-resume `manual_intervention` escalation, `cancel-browser` on a paused task, and - the one that mattered most, since it's the actual point of the credential vault - a second application for the same user correctly took the `LOGIN` branch (not `CREATE_ACCOUNT`) and logged in successfully using the reused, previously-generated credential.
4. **`GenericAdapter` v2 - done, verified live 2026-07-20**: real multi-signal `detect_state` (section 6) and handlers for every state.
   Verified independently against the same live fixture (not just the state machine's own detection): 12/12 states correctly classified using only generic signals (URL substrings, headings, button text, password/file field presence, unchecked-required-checkbox), no fixture-specific selectors.
5. **Mock-ATS fixture extended - done.** Added `landing`/`apply`/`login`/`signup`/`verify-email`/`profile-setup`/`resume-upload`/`resume-parsing` stages via hash routing (`fixtures/ats-sites/mock-ats/index.html`, `app.js`), plus real server-side account storage (`server.py`'s `_ACCOUNTS` dict, replacing an earlier `localStorage`-based draft that couldn't actually validate credential reuse - Playwright's `browser.new_context()` gives each run an isolated storage jar, so client-side storage can't simulate an account surviving across separate login attempts the way a real ATS backend does; this was caught by the credential-reuse verification in item 3 failing against the old draft, not designed in ahead of time).
   No dedicated CI test suite added yet (the live-fixture verification runs in this session covered every state and transition, but as manual/agent-driven runs, not a committed automated test file) - worth adding before this is considered fully "done" for CI purposes.
6. **Dynamic-questions bridge** (section 9) - pure wiring against `ApplicationQuestionAgent`, no new AI logic, done last since nothing else depends on it.
7. **Real ATS validation - done 2026-07-21, all four platforms, see section 13.** Researched Workday, Greenhouse, Lever, and Ashby live (view-only navigation against real job postings, no submission/account-creation/personal-data-entry). Every real finding turned out to be generalizable into the existing generic layer - **no `WorkdayAdapter` or any other platform-specific adapter was built**, a deliberate outcome, not a shortcut: the whole point of `GenericAdapter`'s multi-signal design was to avoid needing one adapter per ATS, and this was the first real test of that bet.

## 12. Decisions (resolved 2026-07-20)

1. **Account creation**: always attempted automatically first.
   `MANUAL_INTERVENTION` triggers only on genuine blockers - CAPTCHA, MFA, email verification, an unsupported flow, or repeated failure - never simply because an account needs to be created.
   `spec.md` Example C's text should be rewritten accordingly once this ships (see section 2/8).
2. **Durability**: Postgres for state and checkpoints, MinIO for files, no container-local persistence beyond a short-lived write buffer.
   Must survive a container restart or redeploy.
3. **Credentials**: build `ats_credentials` + `CredentialCipher`/`FernetCredentialCipher` now, keyed by `CREDENTIAL_ENCRYPTION_KEY` from the environment.
   The interface is the seam for a future real secret manager (Vault/AWS/GCP); that swap is explicitly out of scope for now and must not block this work.
4. **Validation strategy**: both.
   Extend the mock-ATS fixture first so the full state machine is deterministically testable in CI, then validate against a real Workday deployment and refine the adapter from what's actually observed.

## 13. Real-ATS validation findings (2026-07-21)

Priority order per instruction: Workday, Greenhouse, Lever, Ashby. Methodology: `WebSearch` for a live, real job posting on each platform (never a guessed/fabricated URL), then headless Playwright navigation dumping headings/buttons/every form field's name/id/type/geometry/aria attributes at each stage - view-only throughout, no form submission, no real personal data entry, no account creation, consistent with this session's safety constraints.

### 13.1 What each platform confirmed or changed about this design

- **Workday** (NVIDIA posting): confirms the `landing -> apply -> login/create_account -> ... -> application -> review -> submit_ready` sequence and the client-side (no real navigation) transition on Apply that `_wait_for_transition` was already built for. Adds a multi-choice "Start Your Application" screen (Autofill with Resume / Apply Manually / Use My Last Application) between `LANDING` and `LOGIN`, and an OAuth-vs-email choice within the sign-in step itself - both are choices *within* the existing `APPLY`/`LOGIN` states, not new states, and both are already reachable by `_handle_apply`'s generic button-word search rather than needing a dedicated selector. Also has a persistent stepper/breadcrumb ("Create Account/Sign In -> My Information -> My Experience -> Application Questions -> Voluntary Disclosures -> Self Identify -> Review") - a high-confidence structural signal not currently used by `detect_state`, noted as a future strengthening but not required, since the existing signal set already classifies these pages correctly as `APPLICATION`/`REVIEW`.
  Found the honeypot field discussed in section 6/HANDOFF - see 13.2.
- **Greenhouse** (MNTN posting): single-page application form, **no login/account step at all**. This doesn't require a design change - `LOGIN`/`CREATE_ACCOUNT` were already only entered if `_handle_apply` finds an auth choice on the page; a form with none simply proceeds straight into `APPLICATION`. Confirms real reCAPTCHA usage (see 13.2) and a "Quick Apply with MyGreenhouse" account-based fast path (optional, not required - out of scope, since the account-free path already works).
- **Lever** (Palantir posting): also single-page, no login. A cookie-consent banner blocks Apply until dismissed (13.2). Uses hCaptcha, not reCAPTCHA - confirms CAPTCHA handling has to be vendor-agnostic, not reCAPTCHA-specific. Custom application questions are rendered with opaque UUID field names (`cards[<uuid>][field0]`) with no semantic meaning at all - matchable only by the field's rendered label text, never by name/id. This already matches how `FormInspector`/`GenericAdapter`'s label-discovery works (label text drives `FieldMapper`, not the raw name), so no change was needed, but it's worth flagging as the reason name-based heuristics alone would fail entirely on Lever's custom questions.
- **Ashby** (Vanta posting): single-page, no login, reCAPTCHA again. EEO fields carry a reliable naming convention (`..._systemfield_eeoc_gender`, `_eeoc_race`, `_eeoc_veteran_status`) and canonical fields use a `_systemfield_` prefix - informed the EEO keyword fix in 13.2 but wasn't relied on as the sole detection signal (name/id conventions vary by platform; label-based detection is what generalizes).

### 13.2 Hardening implemented (all generic, none of it ATS-specific)

- **Honeypot vs. legitimate near-zero-geometry field** (`browser_worker/services/field_visibility.py`, new): Workday's beecatcher field passes Playwright's `:visible` cleanly (`display:block; visibility:visible; opacity:1`) with a `1px x 0.01px` box. A blunt size threshold can't be the fix, because Ashby's file upload (1x1, behind a styled button), Greenhouse's near-invisible EEO `<select>`, and Lever's not-yet-revealed `eeo[disabilitySignature]` (0x0 until answered) are all *legitimate* near-zero fields on real, live ATS platforms. The signal that actually separates them: a honeypot exists specifically to have no human-discoverable label. Implemented as a multi-signal check - size, then a `type=file` exemption, then a CAPTCHA-response-field-name exemption, then label-discoverability (`aria-label`, `aria-labelledby`, `label[for]`, or a wrapping `<label>`) - not a single cutoff. Wired into both `GenericAdapter.inspect_form` and `MockATSAdapter.inspect_form`.
- **CAPTCHA detection** (`browser_worker/services/captcha_detection.py`, new): `PauseReason.CAPTCHA` existed in `state.py` since section 3 but nothing ever produced it - a real gap given the spec's explicit "no CAPTCHA or anti-bot circumvention of any kind" rule and that three of the four platforms researched use a real CAPTCHA vendor. Vendor-agnostic (reCAPTCHA v2, hCaptcha, Cloudflare Turnstile). Deliberately triggers only on a *visible interactive challenge widget/iframe*, not on the mere presence of a hidden `g-recaptcha-response`/`h-captcha-response` field - invisible reCAPTCHA v3 injects that field on nearly every page load and scores traffic silently in the background, so a naive "field present" check would pause on nearly every Greenhouse/Ashby application regardless of whether a human was ever actually needed. Checked in `worker.py`'s main loop ahead of `adapter.detect_state`, so it fires regardless of which state the page would otherwise classify as, and never attempts to solve or interact with the challenge - only recognizes one is present.
- **Cookie-consent dismissal** (`browser_worker/services/cookie_consent.py`, new): clicks the most privacy-preserving option on a visible banner (reject/decline preferred, accept only as fallback), matching this session's own privacy-first defaults for consent popups. Called once per fresh navigation (`run()`/`resume()`), not every loop tick, since the word lists are broad enough that repeated matching risks misfiring on an unrelated later control.
- **EEO/demographic risk classification** (`backend/app/api/routes/application_questions.py`): `_HIGH_RISK_KEYWORDS` had zero coverage for race/ethnicity/gender/veteran/disability terms before this - confirmed as real, named, required-adjacent fields on three of the four platforms, not a hypothetical category. Fixed directly; `ApplicationQuestionAgent`'s existing hard "never guess high-risk" rule (section 9) now actually applies to them.

### 13.3 Deliberately not built

- **No `WorkdayAdapter`/`GreenhouseAdapter`/`LeverAdapter`/`AshbyAdapter`.** Every real finding across all four platforms was generalizable into `GenericAdapter`/`MockATSAdapter`/`worker.py`'s shared layer. This was the actual test of whether the multi-signal generic design (section 6) could hold up against real ATS platforms without per-site branching, and it held.
- **No new `BrowserState` values** for Workday's "My Experience"/"Voluntary Disclosures"/"Self Identify" stepper steps. All three are already covered by the existing generic `APPLICATION` state (any form page with fields to fill, advance when done) - the EEO/high-risk handling that matters for "Self Identify" specifically is routed by field content (label text, section 13.2's classifier), not by which page state it's found on, so a dedicated state would have added platform-shaped modeling for no behavioral benefit.
- **No stepper/breadcrumb-based detection signal**, despite Workday's being a strong one. The existing signal set (URL, headings, buttons, field presence) already classifies every Workday page correctly; adding this would be strengthening confidence scores, not fixing a gap, and was left for a future pass if a real submission attempt ever surfaces a misclassification the current signals miss.
