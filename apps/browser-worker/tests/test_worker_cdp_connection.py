"""Real Playwright, real Chromium CDP connection tests (no mocks) for the
Hermes-VPS integration path: BrowserWorker.run()/resume() connecting to a
persistent, already-authenticated remote Chrome instance over the Chrome
DevTools Protocol instead of launching a fresh throwaway local browser.

Verified manually first (see conversation) that Playwright's
connect_over_cdp against a real locally-launched Chromium (remote debugging
enabled) behaves exactly as _acquire_browser_and_context assumes: the
connecting client sees the launching browser's existing context (with
whatever pages/cookies it already has), and closing only the connecting
client's handle - never calling .close() on it - leaves the original
browser and its context alive. These tests exercise that same real
contract, not a mock of it - this is "debugging an isolated component"
(the connection-acquisition helper itself), which the project's real-world
testing standard explicitly allows.

No actual Hermes VPS is reachable from this test environment; these tests
prove the code's CDP-handling contract is correct using a real local
Chromium standing in for "some persistent remote Chrome instance" - the
wire protocol (CDP over a ws:// URL) doesn't care whether the far end is
local or remote.
"""
import os

import pytest
from playwright.async_api import async_playwright

from browser_worker.models import ApplicationData
from browser_worker.worker import BrowserWorker

MOCK_ATS_URL = os.environ.get("MOCK_ATS_URL", "http://mock-ats:8080")
_CDP_PORT = 9333


def _make_application_data(label: str) -> ApplicationData:
    return ApplicationData(
        application_id=f"cdp-{label}",
        first_name="Casey",
        last_name="Cdp",
        email=f"cdp-{label}@example.com",
        phone="555-0100",
        linkedin="https://linkedin.com/in/caseycdp",
        work_authorization="yes",
        resume_path="",
        interest=None,
    )


@pytest.mark.asyncio
async def test_local_mode_owns_a_fresh_isolated_context():
    """Default (cdp_url=None): unchanged from before this feature existed -
    a brand-new browser and context, fully owned by the caller."""
    worker = BrowserWorker(headless=True)
    async with async_playwright() as p:
        browser, context, owns_context = await worker._acquire_browser_and_context(p)
        try:
            assert owns_context is True
            assert context.pages == []
        finally:
            await context.close()
            await browser.close()


@pytest.mark.asyncio
async def test_cdp_mode_reuses_the_persistent_connections_existing_context():
    """Connects over CDP to a real (locally-launched, standing in for
    Hermes) Chromium that already has a context with a page open in it -
    proves the returned context is that SAME persistent context (carrying
    its existing page), not a fresh isolated one, which is the entire
    point of the CDP path.

    Asserts via page identity/count rather than a live cookies() re-fetch:
    confirmed independently that Playwright's BrowserContext.cookies()
    doesn't live-sync across two separately-connected CDP clients (the
    connecting client's cookie cache isn't populated by writes made
    through a different client) - a Playwright client-caching quirk
    unrelated to what _acquire_browser_and_context actually does. Page
    identity is a direct, unambiguous proof of same-context reuse instead.
    """
    async with async_playwright() as p:
        persistent_browser = await p.chromium.launch(
            headless=True, args=[f"--remote-debugging-port={_CDP_PORT}"]
        )
        try:
            persistent_context = await persistent_browser.new_context()
            seed_page = await persistent_context.new_page()
            await seed_page.goto(MOCK_ATS_URL)

            worker = BrowserWorker(headless=True, cdp_url=f"http://localhost:{_CDP_PORT}")
            browser, context, owns_context = await worker._acquire_browser_and_context(p)
            try:
                assert owns_context is False
                assert len(context.pages) == 1
                assert context.pages[0].url == seed_page.url
            finally:
                # Deliberately does NOT close context/browser here - that's
                # the whole contract under test: the caller in CDP mode
                # must never tear down the shared connection.
                pass
        finally:
            await persistent_browser.close()


@pytest.mark.asyncio
async def test_run_in_cdp_mode_leaves_the_persistent_browser_running_afterward():
    """End-to-end through BrowserWorker.run() itself (real mock-ats fixture,
    real state machine) - proves run() doesn't call context.close()/
    browser.close() in CDP mode, which would kill a shared persistent
    session other concurrent tasks (or the user's own browsing) depend on."""
    async with async_playwright() as p:
        persistent_browser = await p.chromium.launch(
            headless=True, args=[f"--remote-debugging-port={_CDP_PORT + 1}"]
        )
        try:
            worker = BrowserWorker(headless=True, cdp_url=f"http://localhost:{_CDP_PORT + 1}")
            ctx = worker.make_context(
                session_id="cdp-run-test",
                application_url=MOCK_ATS_URL,
                application_data=_make_application_data("run"),
                user_id="u1",
            )

            await worker.run(ctx)

            # The persistent browser must still be alive and connectable -
            # if run() had called browser.close() on the CDP-connected
            # handle, this reconnect would fail.
            reconnected = await p.chromium.connect_over_cdp(f"http://localhost:{_CDP_PORT + 1}")
            assert len(reconnected.contexts) >= 1
        finally:
            await persistent_browser.close()


@pytest.mark.asyncio
async def test_cdp_url_survives_a_chrome_restart_when_using_the_http_base_form():
    """Regression test for a real finding, documented in HERMES.md: a real
    Chrome DevTools Protocol websocket URL
    (ws://.../devtools/browser/<uuid>) embeds a uuid that's minted fresh on
    every Chrome process start, so a BROWSER_CDP_URL hardcoded to that form
    goes stale the moment Hermes's Chrome restarts (systemd auto-restarts
    it on crash/boot - see HERMES.md's "Hermes facts").

    Proves the fix: pointing connect_over_cdp at the plain http://host:port
    BASE (no uuid in it at all) instead keeps working across a full Chrome
    process restart with the exact same literal URL, because Playwright
    re-resolves the current websocket endpoint from that base on every
    connection. This is what BrowserWorker(cdp_url=...) is documented to
    require - see .env.example's BROWSER_CDP_URL comment.

    Two independent real Chromium processes on the same port (the second
    only started after the first is fully closed) stand in for "Chrome
    restarted" - no mocks. Each real Chrome process mints its own internal
    uuid on launch (this is exactly the mechanism that makes a hardcoded
    ws://.../devtools/browser/<uuid> URL go stale), so successfully
    connecting and using the browser the second time, via the identical
    literal cdp_base string used the first time, is direct proof that the
    http:// base form needs no update across a restart.
    """
    cdp_base = f"http://localhost:{_CDP_PORT + 2}"
    async with async_playwright() as p:
        first_chrome = await p.chromium.launch(
            headless=True, args=[f"--remote-debugging-port={_CDP_PORT + 2}"]
        )
        await p.chromium.connect_over_cdp(cdp_base)
        await first_chrome.close()

        second_chrome = await p.chromium.launch(
            headless=True, args=[f"--remote-debugging-port={_CDP_PORT + 2}"]
        )
        try:
            # Same literal cdp_base as above - no code/config change between
            # "restarts", exactly what a fixed BROWSER_CDP_URL env var means.
            second_connection = await p.chromium.connect_over_cdp(cdp_base)
            context = second_connection.contexts[0] if second_connection.contexts else await second_connection.new_context()
            page = await context.new_page()
            await page.goto(MOCK_ATS_URL)
            assert await page.title() is not None
        finally:
            await second_chrome.close()
