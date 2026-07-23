import logging
import asyncio
import time
import uuid
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
from .models import ApplicationData, Checkpoint
from .adapters import MockATSAdapter, GenericAdapter
from .services import FormInspector, FieldMapper, CheckpointManager
from .services.captcha_detection import detect_captcha_challenge
from .services.cookie_consent import dismiss_cookie_consent
from .state import BrowserState, PauseReason, RunContext, REPLAY_RESUME_STATES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Tuned against the mock-ats fixture and the first four real ATS platforms
# validated (Workday, Greenhouse, Lever, Ashby) - all comfortably finished
# well inside the old budget (40 transitions / 900s). A real, very long
# single-flow application form (confirmed live: Epic's real Avature-hosted
# "Employment Inquiry" section alone has 17+ fields, several needing an
# agent call each, and doesn't persist progress server-side until its own
# internal "Next" completes - hitting the budget mid-section silently
# discards that section's unsaved work, which then has to be redone from
# scratch on the next attempt) can need meaningfully more of both.
MAX_TRANSITIONS = 80
MAX_WALL_CLOCK_SECONDS = 1800
MAX_UNKNOWN_STREAK = 3
# See run_state_machine's progress_snapshot check - 3 strikes before
# concluding a run is genuinely stalled rather than just between two
# almost-identical-looking real steps (e.g. a slow-loading widget that
# briefly re-renders the same fields before something actually advances).
MAX_NO_PROGRESS_STREAK = 3

# run_state_machine's own MAX_WALL_CLOCK_SECONDS check only runs between loop
# iterations, so it can't bound a single operation that hangs mid-iteration
# (e.g. a Playwright action stuck past its own internal timeout expectations).
# This wraps the whole call as a hard backstop - the margin gives the loop's
# own budget check a chance to fire first in the normal case.
_HARD_TIMEOUT_SECONDS = MAX_WALL_CLOCK_SECONDS + 120

# "networkidle" only tracks network activity, not client-side rendering - a
# heavy SPA (confirmed live against a real Ashby posting) can fire
# networkidle while the actual form is still being fetched/hydrated by a
# dynamically-injected JS bundle, leaving detect_state looking at a bare
# "enable javascript to run this app" shell. Rather than pay this wait on
# every navigation (most pages, including every mock-ats state, render well
# within networkidle), it's spent once, only on the specific path that's
# about to give up for good: the very first classification of a run, before
# there's any last_known_state to fall back on.
_FIRST_DETECTION_SETTLE_TIMEOUT_MS = 4000

# Shared between run() and resume() deliberately: a resumed session restores
# real cookies via storage_state (see _persist_storage_state), and a
# different user agent showing up against the same session cookie is
# exactly the kind of anomaly a real site's session-security checks are
# built to flag - resume() using a different UA than the run() that
# actually established the session would undermine the whole point of
# restoring it.
_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


class BrowserWorker:
    """Browser automation state machine.

    Drives an ATS adapter through BrowserState transitions (landing -> apply ->
    login/create_account -> profile_setup -> resume_upload -> resume_parse_wait
    -> application -> review -> submit_ready -> submitted), pausing for human
    approval at submit_ready and for manual intervention wherever automation
    can't safely proceed. See docs/browser-state-machine-design.md.
    """

    def __init__(
        self,
        headless: bool = True,
        checkpoint_dir: str = "/tmp/checkpoints",
        assisted_mode: bool = True,
        db=None,
        browser_session_id: Optional[uuid.UUID] = None,
    ):
        """db/browser_session_id enable durable (Postgres+MinIO) checkpointing.

        Left as None for worker.py's standalone host-based demo entrypoint
        (run_demo.sh), which has no database - CheckpointManager falls back
        to local files in that case. queue_worker.py always supplies both.
        """
        self.headless = headless
        self.assisted_mode = assisted_mode
        self.checkpoint_manager = CheckpointManager(checkpoint_dir, db=db, browser_session_id=browser_session_id)
        self.field_mapper = FieldMapper()
        self.form_inspector = FormInspector()

        # Register adapters (order matters - specific first, generic last)
        self.adapters = [
            MockATSAdapter(),
            GenericAdapter(),  # Fallback
        ]

    def make_context(
        self,
        session_id: str,
        application_url: str,
        application_data: ApplicationData,
        user_id: str,
        ats_platform: str = "generic",
        tenant_key: str = "default",
    ) -> RunContext:
        """Construct a RunContext sharing this worker's FieldMapper instance,
        so learned mappings (once that exists) stay shared across a run."""
        return RunContext(
            session_id=session_id,
            application_url=application_url,
            application_data=application_data,
            user_id=user_id,
            field_mapper=self.field_mapper,
            ats_platform=ats_platform,
            tenant_key=tenant_key,
        )

    async def _navigate(self, page: Page, url: str) -> None:
        """Navigate and wait for the network to settle - but a real, live
        page (confirmed against Epic's real Avature-hosted application
        portal, and matching Workday's /apply route earlier this session)
        can carry persistent background network activity (polling,
        analytics, websockets) that means "networkidle" never fires within
        any reasonable timeout, even though the navigation itself has
        already completed and the page is genuinely usable. Before this,
        that timeout was unhandled and crashed the entire task to a hard
        failed status before the state machine ever got a chance to run -
        exactly the "automation fails silently/uncontrolled" outcome this
        whole architecture exists to prevent. A timeout here just means
        "give up waiting for quiet", not "the page failed to load" - only
        re-raise if the navigation itself didn't happen (DNS/connection
        errors, invalid URLs, etc.), which surface as some other exception
        type entirely.
        """
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
        except PlaywrightTimeoutError:
            logger.warning(f"networkidle wait timed out navigating to {url} - proceeding anyway (page likely still usable)")

    async def _persist_storage_state(self, context: BrowserContext, ctx: RunContext) -> None:
        """Capture cookies/localStorage before the context closes, so a
        later resume() can restore real session state instead of always
        starting from a brand-new, cookie-less browser - see
        CheckpointManager.save_storage_state's docstring for why this
        matters. Called from a finally block, so a failure here must never
        raise (would mask whatever the real run result/error was)."""
        try:
            state = await context.storage_state()
            self.checkpoint_manager.save_storage_state(ctx.session_id, state)
        except Exception as exc:
            logger.warning(f"Failed to capture storage state (non-fatal): {exc}")

    async def run(self, ctx: RunContext) -> dict:
        """Fresh start: navigate to ctx.application_url and run from LANDING."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            try:
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent=_USER_AGENT,
                )
                try:
                    page = await context.new_page()
                    logger.info(f"Navigating to {ctx.application_url}")
                    await self._navigate(page, ctx.application_url)
                    await dismiss_cookie_consent(page)
                    adapter = await self._detect_adapter(page)
                    logger.info(f"Using adapter: {adapter.get_name()}")
                    return await self._run_state_machine_with_timeout(page, adapter, ctx)
                finally:
                    await self._persist_storage_state(context, ctx)
                    await context.close()
            finally:
                await browser.close()

    async def resume(self, ctx: RunContext, approved_for_submit: bool = False) -> dict:
        """Resume a paused session.

        For APPLICATION/REVIEW/SUBMIT_READY checkpoints, replays the
        checkpointed field values page-by-page first (client-side multi-page
        forms reset to page 1 on reload). For every other checkpointed state
        (LOGIN, CREATE_ACCOUNT, EMAIL_VERIFICATION, PROFILE_SETUP, ...), just
        navigates fresh and lets the state machine's own detect_state figure
        out where things actually are now - by the time a human finishes an
        email verification or CAPTCHA, the site's own server-side state has
        changed, so replaying old form data would be wrong.
        """
        ctx.approved_for_submit = approved_for_submit
        checkpoint = await self.checkpoint_manager.load_checkpoint(ctx.session_id)

        # Navigate to the checkpoint's own URL, not the bare application_url -
        # for a hash-routed SPA (like the mock fixture, and realistically many
        # real ATS flows), a fresh load of the bare URL resets to the very
        # first screen, discarding client-side routing state even though
        # server-side state (e.g. a created account) persisted. This bit a
        # live verification run: replay tried to fill fields on a page that
        # was still showing LANDING because navigation used application_url.
        navigate_url = checkpoint.url if checkpoint else ctx.application_url
        storage_state = self.checkpoint_manager.load_storage_state(ctx.session_id)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            try:
                context_kwargs = {"viewport": {"width": 1280, "height": 720}, "user_agent": _USER_AGENT}
                if storage_state:
                    context_kwargs["storage_state"] = storage_state
                    logger.info("Restoring browser session state from a prior run")
                context = await browser.new_context(**context_kwargs)
                try:
                    page = await context.new_page()
                    await self._navigate(page, navigate_url)
                    await dismiss_cookie_consent(page)
                    adapter = await self._detect_adapter(page)

                    if checkpoint:
                        checkpoint_state = None
                        try:
                            checkpoint_state = BrowserState(checkpoint.step)
                        except ValueError:
                            pass

                        if checkpoint_state in REPLAY_RESUME_STATES:
                            logger.info(f"Replaying checkpoint state {checkpoint_state.value} (page {checkpoint.page_number})")
                            replay_error = await self._replay_to_checkpoint(page, adapter, checkpoint)
                            if replay_error:
                                return {"success": False, "error": replay_error, "session_id": ctx.session_id}
                            ctx.filled_fields = dict(checkpoint.filled_fields)
                            ctx.current_page = checkpoint.page_number
                        else:
                            logger.info(f"Structural resume from checkpoint state '{checkpoint.step}' - re-detecting fresh")

                    return await self._run_state_machine_with_timeout(page, adapter, ctx)
                finally:
                    await self._persist_storage_state(context, ctx)
                    await context.close()
            finally:
                await browser.close()

    async def _run_state_machine_with_timeout(self, page: Page, adapter, ctx: RunContext) -> dict:
        """Hard backstop around run_state_machine - see _HARD_TIMEOUT_SECONDS."""
        try:
            return await asyncio.wait_for(
                self.run_state_machine(page, adapter, ctx), timeout=_HARD_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            return await self._escalate(
                page, ctx, PauseReason.REPEATED_FAILURE,
                f"hard timeout - a single operation exceeded the {_HARD_TIMEOUT_SECONDS}s wall-clock budget",
            )

    async def _wait_for_form_content(self, page: Page) -> bool:
        """Best-effort wait for real form content (an input/select/textarea)
        to appear - used only when the very first page classification of a
        run comes back UNKNOWN, right before that would otherwise escalate
        immediately (see _FIRST_DETECTION_SETTLE_TIMEOUT_MS). Returns True
        if something appeared and re-classifying is worth it, False on
        timeout (there's genuinely no form yet, e.g. a plain landing page -
        not an error, just nothing to wait for)."""
        try:
            await page.wait_for_selector(
                "input:visible, select:visible, textarea:visible",
                timeout=_FIRST_DETECTION_SETTLE_TIMEOUT_MS,
            )
            return True
        except Exception:
            return False

    async def run_state_machine(self, page: Page, adapter, ctx: RunContext) -> dict:
        """The primary browser control loop: detect state, checkpoint, act, wait, repeat."""
        ctx.started_at = time.monotonic()
        settled_first_detection = False
        # Detects a stalled run - same state, same filled fields, iteration
        # after iteration - and escalates after a handful of repeats instead
        # of silently burning the entire MAX_TRANSITIONS budget (confirmed
        # live on two real, independent ATS platforms: a form with an
        # optional field the candidate has no data for can never reach
        # SUBMIT_READY, so every loop re-runs the full fill pass forever,
        # including a real, billed AI call per AI-answered question each
        # time). This doesn't fix the misclassification - has_unfilled_
        # visible_field's inability to tell "optional and empty on purpose"
        # from "required and empty" is a real, separate, harder problem -
        # but it turns "80 wasted transitions and dozens of duplicate AI
        # calls before giving up" into "notice the stall after 3 identical
        # iterations and stop", which is safe regardless of *why* nothing
        # is changing.
        no_progress_streak = 0
        last_progress_snapshot: Optional[tuple] = None

        while True:
            ctx.transitions += 1
            if ctx.transitions > MAX_TRANSITIONS or (time.monotonic() - ctx.started_at) > MAX_WALL_CLOCK_SECONDS:
                return await self._escalate(page, ctx, PauseReason.REPEATED_FAILURE, "state machine exceeded transition/time budget")

            # Checked ahead of adapter.detect_state (which has no reason to know
            # about CAPTCHA vendors) so it fires regardless of which BrowserState
            # the page would otherwise classify as - no per-adapter duplication,
            # and the prior state's checkpoint remains the correct resume anchor
            # (same reasoning as _pause_for_manual_intervention below).
            if await detect_captcha_challenge(page):
                ctx.log_action("captcha_detected", url=page.url)
                return await self._escalate(page, ctx, PauseReason.CAPTCHA, "interactive CAPTCHA challenge detected")

            state, confidence = await adapter.detect_state(page)
            logger.info(f"Detected state: {state.value} (confidence={confidence:.2f})")

            if state == BrowserState.UNKNOWN:
                ctx.unknown_streak += 1
                await self.checkpoint_manager.create_checkpoint(
                    session_id=ctx.session_id, page=page, step=BrowserState.UNKNOWN.value,
                    filled_fields=ctx.filled_fields, page_number=ctx.current_page,
                    decision_reasoning=adapter.get_last_detection_reasoning(),
                    field_sources=ctx.field_sources, action_log=ctx.action_log,
                )
                if ctx.last_known_state is None and not settled_first_detection:
                    # No fallback state to retry as, and nothing confirms yet
                    # whether this is a genuinely unsupported page or just a
                    # slow-hydrating SPA (networkidle fired before the real
                    # form rendered - confirmed live against a real Ashby
                    # posting). Spend the settle-wait once before escalating.
                    settled_first_detection = True
                    if await self._wait_for_form_content(page):
                        ctx.unknown_streak = 0
                        continue
                if ctx.unknown_streak >= MAX_UNKNOWN_STREAK or ctx.last_known_state is None:
                    return await self._escalate(page, ctx, PauseReason.UNSUPPORTED_FLOW, "could not classify page state")
                # Retry the last confident handler rather than giving up immediately.
                state = ctx.last_known_state
            else:
                ctx.unknown_streak = 0
                ctx.last_known_state = state
                await self.checkpoint_manager.create_checkpoint(
                    session_id=ctx.session_id, page=page, step=state.value,
                    filled_fields=ctx.filled_fields, page_number=ctx.current_page,
                    decision_reasoning=adapter.get_last_detection_reasoning(),
                    field_sources=ctx.field_sources, action_log=ctx.action_log,
                )

            if state == BrowserState.SUBMITTED:
                confirmation = await adapter.detect_confirmation(page)
                return {
                    "success": True,
                    "status": "submitted",
                    "state": state.value,
                    "confirmed": confirmation.confirmed,
                    "application_id": confirmation.application_id,
                    "session_id": ctx.session_id,
                }

            if state in (BrowserState.MANUAL_INTERVENTION, BrowserState.EMAIL_VERIFICATION):
                reason = PauseReason.EMAIL_VERIFICATION if state == BrowserState.EMAIL_VERIFICATION else PauseReason.UNSUPPORTED_FLOW
                return await self._pause_for_manual_intervention(page, ctx, reason)

            if state == BrowserState.SUBMIT_READY:
                if not ctx.approved_for_submit:
                    logger.info("Reached submit_ready - waiting for user approval")
                    ctx.log_action("await_approval", state=state.value)
                    return {"success": True, "status": "awaiting_approval", "state": state.value, "session_id": ctx.session_id}
                return await self._do_submit(page, adapter, ctx)

            try:
                result = await adapter.handle_state(state, page, ctx)
            except Exception as exc:
                # A handler touches live, unpredictable real-site DOM
                # (inspect_form, fill_field, upload_document, ...) - an
                # uncaught exception here previously crashed the whole task
                # to a hard WorkflowStatus.failed instead of the graceful
                # manual_intervention pause every other failure mode gets
                # (confirmed live: inspect_form's "No visible form found on
                # page" ValueError propagated all the way out). The state
                # machine's entire premise is that automation never fails
                # silently/uncontrolled - any handler exception must
                # degrade to the same human-review path as a handled
                # failure, not bypass it.
                logger.exception(f"Handler for {state.value} raised an unexpected exception")
                ctx.log_action("handle_state", state=state.value, success=False, error=str(exc))
                return await self._escalate(page, ctx, PauseReason.REPEATED_FAILURE, f"handler for {state.value} raised: {exc}")

            ctx.log_action("handle_state", state=state.value, success=result.success, error=result.error)
            if not result.success:
                return await self._escalate(page, ctx, PauseReason.REPEATED_FAILURE, result.error or f"handler for {state.value} failed")

            if ctx.pending_question:
                logger.info(f"Pausing on unanswered question: {ctx.pending_question.get('label')}")
                ctx.log_action("pause_question", field=ctx.pending_question.get("field_name"), label=ctx.pending_question.get("label"))
                return {
                    "success": True,
                    "status": "paused_question",
                    "state": state.value,
                    "pending_question": ctx.pending_question,
                    "session_id": ctx.session_id,
                }

            # Field *names*, not values - an AI-generated answer can come
            # back slightly differently worded each time (non-zero
            # temperature), which would make an items()-based snapshot
            # look "different" every single iteration even though it's
            # genuinely the same fields being re-answered in a stuck loop.
            # Confirmed live: a real Ashby posting with two AI-answered
            # required custom questions never tripped the original
            # items()-based check at all, for exactly this reason.
            progress_snapshot = (state, tuple(sorted(ctx.filled_fields.keys())))
            if progress_snapshot == last_progress_snapshot:
                no_progress_streak += 1
                if no_progress_streak >= MAX_NO_PROGRESS_STREAK:
                    return await self._escalate(
                        page, ctx, PauseReason.REPEATED_FAILURE,
                        f"no progress after {no_progress_streak} consecutive {state.value} iterations "
                        "(same state, same filled fields each time)",
                    )
            else:
                no_progress_streak = 0
                last_progress_snapshot = progress_snapshot

            await self._wait_for_transition(page)

    async def _do_submit(self, page: Page, adapter, ctx: RunContext) -> dict:
        logger.info("Submitting application")
        ctx.log_action("submit", url=page.url)
        submit_result = await adapter.submit(page)
        if not submit_result.success:
            return await self._escalate(page, ctx, PauseReason.REPEATED_FAILURE, submit_result.error or "submit failed")

        await page.wait_for_timeout(1500)
        confirmation = await adapter.detect_confirmation(page)
        await self.checkpoint_manager.create_checkpoint(
            session_id=ctx.session_id, page=page, step=BrowserState.SUBMITTED.value,
            filled_fields=ctx.filled_fields, page_number=ctx.current_page,
            field_sources=ctx.field_sources, action_log=ctx.action_log,
        )
        return {
            "success": True,
            "status": "submitted",
            "confirmed": confirmation.confirmed,
            "application_id": confirmation.application_id,
            "session_id": ctx.session_id,
        }

    async def _escalate(self, page: Page, ctx: RunContext, reason: PauseReason, message: str) -> dict:
        logger.warning(f"Escalating to manual intervention ({reason.value}): {message}")
        ctx.log_action("escalate", reason=reason.value, message=message)
        return await self._pause_for_manual_intervention(page, ctx, reason, detail=message)

    async def _pause_for_manual_intervention(
        self, page: Page, ctx: RunContext, reason: PauseReason, detail: Optional[str] = None
    ) -> dict:
        """Deliberately does NOT write its own checkpoint.

        The main loop already checkpoints the real BrowserState reached just
        before this was called (e.g. "email_verification", "application",
        "login") - that's the correct resume anchor. Writing a synthetic
        "manual_intervention" checkpoint on top would overwrite it and force
        every pause, regardless of cause, into structural resume (re-navigate
        + re-detect) even when the pause happened mid-replay-resume state,
        which would silently discard replay-in-progress data. Generic by
        design - no ATS-specific branching here at all.
        """
        return {
            "success": True,
            "status": "manual_intervention",
            "state": BrowserState.MANUAL_INTERVENTION.value,
            "pause_reason": reason.value,
            "detail": detail,
            "session_id": ctx.session_id,
        }

    async def _wait_for_transition(self, page: Page) -> None:
        """Wait for either real navigation or SPA-style DOM mutation, whichever
        comes first - a real ATS (Workday in particular) is heavily client-side
        rendered, exactly like the mock fixture's hash-routed stages."""
        try:
            mutation_wait = asyncio.ensure_future(page.evaluate("""
                () => new Promise((resolve) => {
                    let resolved = false;
                    const done = () => { if (!resolved) { resolved = true; resolve(true); } };
                    const observer = new MutationObserver(done);
                    observer.observe(document.body, { childList: true, subtree: true, attributes: true });
                    setTimeout(done, 2500);
                })
            """))
            navigation_wait = asyncio.ensure_future(page.wait_for_load_state("networkidle", timeout=3000))

            done, pending = await asyncio.wait([mutation_wait, navigation_wait], return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            for task in done:
                task.exception()  # consume any exception so it isn't logged as "never retrieved"
        except Exception as exc:
            logger.debug(f"_wait_for_transition signal race raised (non-fatal): {exc}")

        # Brief settle window regardless, since detect_state runs immediately after.
        await page.wait_for_timeout(300)

    async def _replay_to_checkpoint(self, page: Page, adapter, checkpoint: Checkpoint) -> Optional[str]:
        """Re-fill pages 1..checkpoint.page_number from checkpoint.filled_fields.

        Returns an error message on failure, or None on success.

        checkpoint.filled_fields is CheckpointManager's *redacted* copy. Login/
        signup credential fields are never routed through this dict at all
        (see RunContext.credential) specifically so this replay can never type
        a redaction placeholder into a live form.
        """
        current_page = 1
        while True:
            form = await adapter.inspect_form(page)

            for field in form.fields:
                if field.name not in checkpoint.filled_fields:
                    continue
                value = checkpoint.filled_fields[field.name]
                if field.input_type == "file":
                    await adapter.upload_document(page, field, value)
                else:
                    await adapter.fill_field(page, field, str(value))

            if current_page >= checkpoint.page_number:
                return None

            nav_result = await adapter.navigate_next(page)
            if not nav_result.success:
                return f"Failed to replay to page {current_page + 1}: {nav_result.error}"
            current_page = nav_result.page_number

    async def _detect_adapter(self, page: Page):
        """Detect which adapter can handle this page"""
        for adapter in self.adapters:
            if await adapter.detect(page):
                return adapter

        # Should never reach here since GenericAdapter always returns True
        return self.adapters[-1]


async def main():
    """Example usage - standalone host-based demo (see run_demo.sh/QUICKSTART.md).

    Runs headed against a local mock-ats instance, no database - CheckpointManager
    falls back to local files since db/browser_session_id aren't supplied.
    """
    worker = BrowserWorker(headless=False, assisted_mode=True)

    app_data = ApplicationData(
        application_id="test_001",
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        phone="555-0123",
        linkedin="https://linkedin.com/in/johndoe",
        work_authorization="yes",
        resume_path="/tmp/resume.pdf",
        interest="I am excited about this opportunity to contribute to your team.",
    )

    ctx = worker.make_context(
        session_id="app_test_001",
        application_url="http://localhost:8080",
        application_data=app_data,
        user_id="demo-user",
    )

    result = await worker.run(ctx)
    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
