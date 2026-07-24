# Hermes VPS Integration Map

Single entry point for running this platform against Hermes (a persistent,
already-authenticated remote Chrome instance) instead of a local throwaway
browser. Dense index, not a tutorial - follow the links.

## Status

- Done: `BrowserWorker` can connect to a remote Chrome over CDP and reuse its
  existing (logged-in) context. Verified against a real local Chromium
  standing in for Hermes; not yet verified against the actual Hermes VPS.
- Blocked on: nothing in this repo talks to Hermes yet - no tunnel script, no
  systemd/supervisor config, no documented port. Not just undocumented; not built.
  See "Open questions" below.
- Not started: credential-vault auth model change, agent-driven manual-intervention
  pause points (see "Not yet done" below).

## Run it

- General deploy (local or remote): [`QUICKSTART.md`](./QUICKSTART.md), driven by
  [`setup-portable.sh`](./setup-portable.sh) - already treats "a Hermes agent server"
  as the canonical remote-deploy example.
- `./setup-portable.sh your-hermes-hostname-or-ip` from a fresh clone; brings up
  Postgres/Redis/MinIO/API/job-worker/browser-worker/web/mock-ats via `docker-compose.yml`.
- To point browser-worker at Hermes's persistent Chrome instead of a local
  throwaway one: set `BROWSER_CDP_URL` in `.env` (documented at
  [`.env.example:99-106`](./.env.example)) to a **privately-tunneled** `ws://` URL -
  never a bare public `host:port`, the CDP port grants full control of a browser
  logged into real accounts. Wired through
  [`docker-compose.yml:165`](./docker-compose.yml) →
  [`queue_worker.py:237-238`](./apps/browser-worker/browser_worker/queue_worker.py#L237-L238) →
  `BrowserWorker(cdp_url=...)`.
- Tests: `docker compose exec -e AI_PROVIDER=mock api python -m pytest -q` (backend),
  `docker exec job_automation_browser_worker python -m pytest -q` (browser-worker).

## Core CDP-connection code

- [`worker.py:77-100`](./apps/browser-worker/browser_worker/worker.py#L77-L100) -
  `BrowserWorker.__init__`, `cdp_url` param.
- [`worker.py:154-188`](./apps/browser-worker/browser_worker/worker.py#L154-L188) -
  `_acquire_browser_and_context`: local mode launches+owns a fresh browser/context
  (current default, unchanged behavior); CDP mode connects via `connect_over_cdp`
  and reuses `browser.contexts[0]` (the persistent, already-logged-in profile)
  instead of creating an isolated one.
- [`worker.py:203-224`](./apps/browser-worker/browser_worker/worker.py#L203-L224) (`run`) and
  [`worker.py:226-290`](./apps/browser-worker/browser_worker/worker.py#L226-L290) (`resume`) -
  storage-state save/restore (relaunch continuity) is skipped in CDP mode since the
  connection's context already *is* the persistent session. Ownership-scoped cleanup
  (CDP mode only ever closes the page/tab it opened, never the shared context/browser
  other tasks or the user's own browsing depend on) is at
  [`worker.py:282-290`](./apps/browser-worker/browser_worker/worker.py#L282-L290).
- [`test_worker_cdp_connection.py`](./apps/browser-worker/tests/test_worker_cdp_connection.py) -
  real-Chromium (no mocks) proof of the connect/reuse/non-close contract; explains
  a Playwright cross-client cookie-cache quirk encountered while writing it.
- `render_server.py` (job-posting text extraction) deliberately **not** wired to
  CDP/Hermes - stateless anonymous fetches, no benefit from a real logged-in
  identity, and mixing real cookies into it would be pure downside. See its
  module docstring: [`render_server.py:1-19`](./apps/browser-worker/browser_worker/render_server.py#L1-L19).

## Hard rule that does not change on Hermes

Never solve, bypass, or circumvent a CAPTCHA/anti-bot challenge, regardless of
who or what is driving the browser. Detection-only, by design:
[`captcha_detection.py:1-20`](./apps/browser-worker/browser_worker/services/captcha_detection.py#L1-L20).
Pause reasons a run can stop on:
[`state.py:30-38`](./apps/browser-worker/browser_worker/state.py#L30-L38)
(`CAPTCHA`, `MFA`, `EMAIL_VERIFICATION`, `UNSUPPORTED_FLOW`, `REPEATED_FAILURE`, `USER_REVIEW`).
On Hermes, what changes is *who* answers a non-CAPTCHA pause (an agent inspecting
the live page instead of a human polling `/browser-status`) - not whether CAPTCHA
gets solved. It doesn't, ever.
The pause/resume API a future agent would call instead of a human:
[`browser_automation.py`](./backend/app/api/routes/browser_automation.py) -
`start-browser`, `browser-status`, `approve-submit`, `resume-manual-intervention`,
`answer-pending-question`, `cancel-browser`, `replay`.

## Not yet done

- Auth model: [`ats_credential_vault.py`](./backend/app/services/ats_credential_vault.py) +
  [`credential_vault_client.py`](./apps/browser-worker/browser_worker/services/credential_vault_client.py) +
  [`credential_cipher.py`](./backend/app/core/credential_cipher.py) currently issue and
  encrypt throwaway per-application ATS credentials. A persistent Hermes identity
  (real Gmail/GitHub already logged in) shrinks this to account bookkeeping rather
  than credential issuance - needs a design decision before changing.
- Agent-driven manual intervention: pause points still surface via
  `queue_worker.py`'s `WorkflowTask`/`BrowserSession` status
  (see [`queue_worker.py:279-316`](./apps/browser-worker/browser_worker/queue_worker.py#L279-L316))
  for a human to answer through [`browser_automation.py`](./backend/app/api/routes/browser_automation.py)
  above. No mechanism (polling loop, webhook, or otherwise) yet lets an agent answer
  these on Hermes instead - not even a design sketch exists.
- Network security for the CDP port is entirely an infra-side concern (SSH tunnel
  or private network on Hermes itself) - nothing in this repo enforces or implements
  it beyond the `.env.example` warning.
- CI ([`.github/workflows/browser-worker-tests.yml`](./.github/workflows/browser-worker-tests.yml))
  never sets `BROWSER_CDP_URL` - the CDP path has zero automated coverage beyond
  manually running `test_worker_cdp_connection.py`.

## Codebase map (other docs)

- [`README.md`](./README.md) - project overview, quick start, structure.
- [`ARCHITECTURE.md`](./ARCHITECTURE.md) - full system design diagram.
- [`spec.md`](./spec.md) - product spec; section 14 covers browser automation.
- [`docs/browser-state-machine-design.md`](./docs/browser-state-machine-design.md) -
  `BrowserState`/adapter/checkpoint design this whole worker implements.
- [`apps/browser-worker/README.md`](./apps/browser-worker/README.md),
  [`apps/browser-worker/QUICKSTART.md`](./apps/browser-worker/QUICKSTART.md) -
  **stale, do not follow literally**: both predate the docker-compose deploy model
  (reference `ssh bhead` / `/home/brian/job_automation`) and document a
  `process_application()`/`resume_from_checkpoint()` API that no longer exists -
  `worker.py` only has `run()`/`resume()` now. Kept linked only because some
  prose in them (adapter list, field-mapping notes) is still accurate; verify
  against actual code before trusting anything procedural in these two.
- [`backend/app/ai_gateway/README.md`](./backend/app/ai_gateway/README.md) -
  AI provider gateway (mock/Anthropic/OpenAI/DeepSeek).
- [`backend/SETUP.md`](./backend/SETUP.md) - backend-only setup.
- [`HANDOFF.md`](./HANDOFF.md) - prior session handoff notes. (`PROJECT_STATUS.md`/
  `FINAL_STATUS.md` deliberately omitted - same pre-Docker `ssh bhead` model as the
  two docs above, superseded and redundant with HANDOFF.md; don't follow them.)

## Open questions (only the human can answer these)

- Hermes's actual hostname/IP and the port its Chrome instance exposes CDP on.
- Does a tunnel to that port already exist, or does something here need to open
  one (SSH `-L` forward, WireGuard, etc.)?
- Is Chrome already running on Hermes with `--remote-debugging-port` under some
  supervisor, or does that also need to be stood up?
- Topology: does browser-worker run *on* Hermes itself (CDP reachable via
  `localhost`), or does it reach Hermes's CDP port from wherever `docker compose`
  runs, over a network tunnel? Changes what "privately-tunneled" means in practice.
- Whose identity is logged into Hermes's persistent Chrome profile - single shared
  account, consistent with this being a single-user platform (see README.md)?
- What should actually answer a manual-intervention pause on Hermes - a polling
  loop, a webhook, a live Claude Code session watching `browser-status`? No
  mechanism is chosen yet, not even provisionally.
