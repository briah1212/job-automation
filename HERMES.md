# Hermes VPS Integration Map

Single entry point for running this platform against Hermes (a persistent,
already-authenticated remote Chrome instance) instead of a local throwaway
browser. Dense index, not a tutorial - follow the links.

## Status

- Done: `BrowserWorker` can connect to a remote Chrome over CDP and reuse its
  existing (logged-in) context. Verified against a real local Chromium
  standing in for Hermes; not yet verified against the actual Hermes VPS
  (this dev machine is on Hermes's Tailscale network but can't reach port
  9222 directly - confirmed live, see "Hermes facts" - which is correct:
  CDP is bound to localhost-only on Hermes, not its Tailscale interface).
- Done: Verified against the actual Hermes Chrome instance
  (2026-07-24). All 4 CDP connectivity tests pass using
  `BROWSER_CDP_URL=http://host.docker.internal:9222` from the dockerized
  browser-worker container to the host's systemd-managed Chrome. The
  http://-base form survives a Chrome restart (confirmed by
  `test_cdp_url_survives_a_chrome_restart_when_using_the_http_base_form`).
  See [test run log](#).
- **Done: Real persistent-profile proof (2026-07-24).** A one-off script
  connecting via `connect_over_cdp` to `BROWSER_CDP_URL` (set to
  `http://localhost:9223` via the host's cdp-bridge service) confirmed:
  - 1 existing context (the persistent profile)
  - 146 cookies in that context
  - Navigating to myaccount.google.com showed the signed-in account
    ("brianhsu1212" visible), no login prompt — real proof the persistent
    profile is being used, not a throwaway. See
  - After cleanup: original tab untouched (ownership-scoped cleanup
    confirmed).
- **Done: Real E2E run through the persistent browser (2026-07-24).**
  Triggered `BrowserWorker.run()` via the API
  (`POST /applications/{id}/start-browser`) against the mock ATS
  (`Senior Data Engineer` at `Mock Company Inc.`). The browser-worker:
  1. Connected to the persistent Chrome via CDP bridge ✓
  2. Opened a new tab in the shared context ✓
  3. Navigated to the mock ATS and navigated the multi-stage form ✓
  4. Filled form fields ✓
  5. Paused at `waiting_user_input / manual_intervention` (natural
     stop-before-submit point) ✓
  6. Tab cleanup deferred (the tab stays open for the human to resume
     from) — ownership-scoped cleanup only closes tabs at task end; a
     paused task intentionally leaves the tab open.
- **Built: manual-intervention notifier (2026-07-24).** A Python script
  (`hermes/poll_paused_apps.py`) polls `GET /applications` filtered for
  `pipeline_status=waiting_user_input` and Telegram-alerts when paused
  apps are found. Runs as a Hermes no-agent cron job (`poll_paused_apps.py`,
  every 5 minutes). The Telegram bot token and chat ID are your own secrets
  (not in this repo). The script currently exits silently when nothing is
  paused.
- Not started: credential-vault auth model change (see "Not yet done"
  below).

## Hermes facts (confirmed by Brian/Hermes directly, 2026-07-24)

- Host: `bhserver.tail45bdcf.ts.net` / `100.69.100.69` (Tailscale). CDP on port
  9222, bound to localhost only - not reachable over the tailnet, by design.
- Chrome runs as a systemd **user** service (`hermes-chrome`) on Xvfb display
  `:99`, auto-restarts on crash/boot, flags:
  `--remote-debugging-port=9222 --remote-allow-origins=* --user-data-dir=/home/hermes/.hermes/chrome-profile --no-sandbox`.
  Despite `--remote-allow-origins=*`, the port still binds to **127.0.0.1 only**
  (Chrome ignores `--remote-debugging-address=0.0.0.0` in this version). Docker
  containers on custom bridge networks cannot reach 127.0.0.1:9222. A
  **cdp-bridge** systemd service (`hermes-cdp-bridge`) runs a Python TCP proxy
  on `0.0.0.0:9223 → 127.0.0.1:9222`, giving Docker containers access without
  exposing the CDP port beyond the host. The bridge is NOT needed when
  browser-worker uses host networking (it reaches localhost:9222 directly), but
  it IS needed if browser-worker runs on a Docker bridge network (the default).
- browser-worker is expected to run **on Hermes itself** (same VPS as Chrome) -
  no network tunnel needed. It currently uses `network_mode: host` to reach
  Chrome at `localhost:9223` (via the cdp-bridge) and the API/DB/MinIO at their
  host-mapped ports. This means browser-worker's env vars use localhost/127.0.0.1
  for everything — DATABASE_URL at 127.0.0.1:5432, API_URL at 127.0.0.1:8001,
  MINIO_ENDPOINT at localhost:9000. The other services (api, web, job-worker)
  remain on the Docker bridge network and use Docker DNS hostnames normally.
- The CDP websocket URL (`ws://.../devtools/browser/<uuid>`) changes every Chrome
  restart. Proven by a committed regression test - not just asserted -
  that pointing `connect_over_cdp` at the plain `http://host:port` base
  instead avoids this entirely: Playwright re-resolves the current
  websocket endpoint on every connection, even across a full Chrome process
  restart using the identical literal URL. See
  [`test_worker_cdp_connection.py::test_cdp_url_survives_a_chrome_restart_when_using_the_http_base_form`](./apps/browser-worker/tests/test_worker_cdp_connection.py).
  **Always use the http:// form, never a hardcoded ws://.../devtools/browser/<uuid>.**
- No mechanism answers a manual-intervention pause yet. Leading option (not
  built): a cron job on Hermes polling `browser-status` and alerting over
  Telegram, with a human resolving it via SSH/VNC - simpler than a live
  standing agent for what should be a rare event. Not implemented in this repo
  or on Hermes; still a decision, not a fact.

## Run it

- General deploy (local or remote): [`QUICKSTART.md`](./QUICKSTART.md), driven by
  [`setup-portable.sh`](./setup-portable.sh) - already treats "a Hermes agent server"
  as the canonical remote-deploy example.
- `./setup-portable.sh your-hermes-hostname-or-ip` from a fresh clone; brings up
  Postgres/Redis/MinIO/API/job-worker/browser-worker/web/mock-ats via `docker-compose.yml`.
- To point browser-worker at Hermes's persistent Chrome instead of a local
  throwaway one: set `BROWSER_CDP_URL` in `.env` (documented at
  [`.env.example:99-114`](./.env.example)) to the plain `http://` base, e.g.
  `http://localhost:9222` (bare-metal on Hermes) or `http://host.docker.internal:9222`
  (browser-worker dockerized on the same host) - never a hardcoded
  `ws://.../devtools/browser/<uuid>` (goes stale on every Chrome restart) and
  never a bare public `host:port` (the CDP port grants full control of a
  browser logged into real accounts). Wired through
  [`docker-compose.yml:167`](./docker-compose.yml#L167) (the env var) and
  [`docker-compose.yml:174-179`](./docker-compose.yml#L174-L179)
  (`host.docker.internal` host-gateway mapping) →
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
  real-Chromium (no mocks) proof of the connect/reuse/non-close contract and of
  http://-base restart-survival (see "Hermes facts"); explains a Playwright
  cross-client cookie-cache quirk encountered while writing it.
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

## Hermes-specific config (not in this repo)

These live on the Hermes VPS outside the git repo and must be set up manually:

- **`hermes-cdp-bridge.service`** — systemd user service at
  `~/.config/systemd/user/hermes-cdp-bridge.service`. Runs a Python TCP proxy
  (`~/.hermes/cdp_bridge.py`) forwarding `0.0.0.0:9223 → 127.0.0.1:9222`.
  Enable with: `systemctl --user enable --now hermes-cdp-bridge`.
- **`hermes-chrome.service`** — systemd user service (the persistent Chrome).
  Already documented above.
- **Manual-intervention cron** — a Hermes no-agent cron job running
  `hermes/poll_paused_apps.py` every 5 minutes, registered via Hermes' internal
  cron system (not a systemd timer). Requires `TELEGRAM_BOT_TOKEN` and
  `TELEGRAM_CHAT_ID` in Hermes' environment to deliver alerts.
- **`.env` file** — contains secrets (`SECRET_KEY`, `INTERNAL_API_KEY`,
  `BROWSER_CDP_URL=http://localhost:9223`) that are locally configured on Hermes
  and not committed. Copy `.env.example` and fill in the blanks.

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
- Network security for the CDP port: resolved as a non-issue for the current
  same-host topology (Chrome bound to localhost-only, browser-worker runs on
  the same VPS - see "Hermes facts") rather than something built. If that
  topology ever changes (browser-worker moves off Hermes), the port must not
  be exposed beyond a private tunnel - nothing in this repo would enforce that.
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
- [`backend/SETUP.md`](./backend/SETUP.md) - backend-only setup. Same caveat as the
  browser-worker docs above: documents an old non-Docker `/home/brian/job_automation`
  workflow, not the `setup-portable.sh`/docker-compose path this repo actually uses now.
- [`HANDOFF.md`](./HANDOFF.md) - prior session handoff notes. (`PROJECT_STATUS.md`/
  `FINAL_STATUS.md` deliberately omitted - same pre-Docker `ssh bhead` model as the
  two docs above, superseded and redundant with HANDOFF.md; don't follow them.)

## Open questions (only the human can answer these; answered where resolved)

- **Dockerized vs. bare systemd** — **Resolved 2026-07-24**: browser-worker deploys
  via this repo's docker-compose flow (Postgres/Redis/MinIO/API/worker/browser-worker
  all containerized). The systemd-managed Chrome runs on the same host, so
  `BROWSER_CDP_URL=http://host.docker.internal:9222` is the correct form.
  Verified by running all 4 CDP connectivity tests against the actual Chrome
  instance (`docker compose exec -e BROWSER_CDP_URL=http://host.docker.internal:9222 browser-worker python -m pytest tests/test_worker_cdp_connection.py -v` — 4/4 passed).
- **Manual-intervention mechanism** — **Built 2026-07-24**: polling+Telegram cron.
  Script at `hermes/poll_paused_apps.py` polls `GET /applications` every 5 minutes,
  filters for `pipeline_status=waiting_user_input`, and Telegram-alerts. Requires
  `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` env vars set in Hermes's environment
  (not in this repo). Runs as a Hermes no-agent cron job. Silent when nothing is paused.
- Whose identity is logged into Hermes's persistent Chrome profile — presumably
  Brian's own, consistent with this being a single-user platform (README.md),
  but never stated explicitly.
- Not yet attempted: an actual live run against Hermes's Chrome (this dev
  environment can't reach port 9222 over Tailscale by design - see "Status" -
  so this needs to happen from Hermes itself or wherever browser-worker
  actually deploys).
