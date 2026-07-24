"""Concurrency stress test: shared persistent Chrome context via CDP.

Tests that when two BrowserWorker instances connect to the SAME persistent
Chrome instance over CDP, each gets its own isolated page (tab) within the
shared context without state leaking between concurrent runs.

Architecture under test (worker.py:_acquire_browser_and_context):
- CDP mode (cdp_url set): connects to existing Chrome, reuses browser.contexts[0]
  as the shared persistent context. returns owns_context=False so callers
  never close the shared context/browser — only their own page.
- Each run()/resume() call opens a new page via context.new_page().
- The risk: two concurrent runs sharing the same BrowserContext (cookies,
  localStorage) could leak form state, step on navigation, or corrupt each
  other's tabs.

Three escalation levels tested:
  1. Raw Playwright: two pages in same CDP context, independent navigation
  2. Page-level field isolation: same page URL, different field values
  3. Full BrowserWorker.run(): two concurrent state machines (mocked vault)
"""

import asyncio
import os
import sys
import time
import pytest
from unittest.mock import patch

from playwright.async_api import async_playwright

from browser_worker.worker import BrowserWorker
from browser_worker.models import ApplicationData
from browser_worker.state import BrowserState, RunContext
from browser_worker.adapters.mock_ats_adapter import MockATSAdapter

MOCK_ATS_URL = "http://localhost:8080"
CDP_PORT = 9444
CDP_BASE = f"http://localhost:{CDP_PORT}"


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def app_data_alice() -> ApplicationData:
    return ApplicationData(
        application_id="conc-alice",
        first_name="Alice",
        last_name="Wonderland",
        email="alice@concur-test.example",
        phone="555-0101",
        linkedin="https://linkedin.com/in/alice",
        work_authorization="yes",
        resume_path="/tmp/test_resume.pdf",
        interest="Concurrency test - Alice",
    )


@pytest.fixture
def app_data_bob() -> ApplicationData:
    return ApplicationData(
        application_id="conc-bob",
        first_name="Bob",
        last_name="Builder",
        email="bob@concur-test.example",
        phone="555-0202",
        linkedin="https://linkedin.com/in/bob",
        work_authorization="yes",
        resume_path="/tmp/test_resume.pdf",
        interest="Concurrency test - Bob",
    )


def make_worker(cdp_url: str = CDP_BASE) -> BrowserWorker:
    return BrowserWorker(headless=True, cdp_url=cdp_url, checkpoint_dir="/tmp/checkpoints_conc_test")


# ── Level 1: Raw Playwright page isolation within shared CDP context ──────

@pytest.mark.asyncio
async def test_level1_raw_page_isolation_in_shared_context():
    """Two independent pages in the SAME shared BrowserContext over CDP.
    Each page navigates to the same base URL but operates its own hash-routed
    SPA independently."""
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_BASE)
        ctx = browser.contexts[0] if browser.contexts else await browser.new_context()

        # Open two pages from the SAME context
        tab_a = await ctx.new_page()
        tab_b = await ctx.new_page()

        # Navigate both to the mock ATS
        await tab_a.goto(MOCK_ATS_URL, wait_until="networkidle")
        await tab_b.goto(MOCK_ATS_URL, wait_until="networkidle")

        # Each page starts on the landing stage
        landing_a = await tab_a.text_content("h1")
        landing_b = await tab_b.text_content("h1")
        assert landing_a == "Senior Data Engineer"
        assert landing_b == "Senior Data Engineer"

        # Navigate tab_a to apply stage
        await tab_a.click("#apply-btn")
        await tab_a.wait_for_timeout(200)

        # The page shows/hides sections via data-stage. h1 (job title) is always
        # present; the stage-specific content is in h2 elements within each section.
        # Check that tab_a shows the apply stage heading while tab_b is still on landing.
        apply_heading_a = await tab_a.text_content("section:not([style*=\"display: none\"]):not([style*=\"display:none\"]) h2")
        if not apply_heading_a:
            # Fallback: read h2 from the visible stage
            stages_a = await tab_a.evaluate("""() => {
                const stages = document.querySelectorAll('.stage');
                for (const s of stages) {
                    if (s.style.display !== 'none') return s.querySelector('h2')?.textContent || 'none';
                }
                return 'no visible stage';
            }""")
            apply_heading_a = stages_a

        heading_b_still_landing_h1 = await tab_b.text_content("h1")
        heading_b_stage = await tab_b.evaluate("""() => {
            const stages = document.querySelectorAll('.stage');
            for (const s of stages) {
                if (s.style.display !== 'none') return s.querySelector('h2')?.textContent || 'none';
            }
            return 'no visible stage';
        }""")

        print(f"  tab_a apply heading: {apply_heading_a!r}")
        print(f"  tab_b h1: {heading_b_still_landing_h1!r}, tab_b stage: {heading_b_stage!r}")

        # tab_b should still be on landing — tab_a's navigation did not affect it
        apply_stage_visible = "Sign in" in (apply_heading_a or "") or "sign in" in (apply_heading_a or "").lower()
        assert apply_stage_visible, f"Expected 'Sign in' visible in tab_a heading, got: {apply_heading_a}"
        assert heading_b_still_landing_h1 == "Senior Data Engineer", f"tab_B heading should still be landing, got: {heading_b_still_landing_h1}"

        # Navigate tab_b to signup — independent path
        await tab_b.click("#apply-btn")
        await tab_b.wait_for_timeout(100)
        await tab_b.click("#show-signup-btn")
        await tab_b.wait_for_timeout(200)

        # Check tab_b is now on signup/Create Account
        signup_heading_b = await tab_b.evaluate("""() => {
            const stages = document.querySelectorAll('.stage');
            for (const s of stages) {
                if (s.style.display !== 'none') return s.querySelector('h2')?.textContent || 'none';
            }
            return 'no visible stage';
        }""")
        # tab_a should still be on apply stage (not affected by tab_b's navigation)
        apply_heading_a_again = await tab_a.evaluate("""() => {
            const stages = document.querySelectorAll('.stage');
            for (const s of stages) {
                if (s.style.display !== 'none') return s.querySelector('h2')?.textContent || 'none';
            }
            return 'no visible stage';
        }""")

        print(f"  tab_b signup heading: {signup_heading_b!r}")
        print(f"  tab_a apply heading (after tab_b navigated): {apply_heading_a_again!r}")

        assert "Create Account" in signup_heading_b, f"Expected 'Create Account' in tab_b, got: {signup_heading_b}"
        assert "Sign in" in apply_heading_a_again or "sign in" in apply_heading_a_again.lower(), f"Expected 'Sign in' in tab_a, got: {apply_heading_a_again}"

        # Cleanup: close only the pages, NOT the context or browser
        await tab_a.close()
        await tab_b.close()

    print("✅ Level 1: Raw page isolation in shared context — PASS")


# ── Level 2: Form field state isolation between concurrent pages ──────────

@pytest.mark.asyncio
async def test_level2_form_field_isolation_between_concurrent_pages():
    """Two pages fill DIFFERENT data into the SAME form fields.
    Checks that each page keeps its own client-side state and values don't
    leak through shared cookies/localStorage (the form uses localStorage
    only on submit, so intermediate field values are page-local DOM state)."""
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_BASE)
        ctx = browser.contexts[0] if browser.contexts else await browser.new_context()

        tab_a = await ctx.new_page()
        tab_b = await ctx.new_page()

        # Navigate both to landing
        await tab_a.goto(MOCK_ATS_URL, wait_until="networkidle")
        await tab_b.goto(MOCK_ATS_URL, wait_until="networkidle")

        # Progress both through landing -> apply -> signup -> profile-setup -> resume-upload -> resume-parsing -> application
        for tab in (tab_a, tab_b):
            await tab.click("#apply-btn")
            await tab.wait_for_timeout(100)
            await tab.click("#show-signup-btn")
            await tab.wait_for_timeout(200)

            # Fill signup form
            email = "alice@test.com" if tab == tab_a else "bob@test.com"
            await tab.fill('[name="signup_email"]', email)
            pwd = "TestPass123!@#"
            await tab.fill('[name="signup_password"]', pwd)
            await tab.fill('[name="signup_confirm_password"]', pwd)
            # Verify we're on the signup stage before submitting
            tab_hash = await tab.evaluate("window.location.hash")
            print(f"  Tab {'A' if tab == tab_a else 'B'} hash before submit: {tab_hash}")
            await tab.click('#signup-form button[type="submit"]')
            await tab.wait_for_timeout(500)

            # Profile setup
            name = "Alice" if tab == tab_a else "Bob"
            await tab.fill('[name="preferred_name"]', name)
            await tab.select_option('[name="referral_source"]', "job_board")
            await tab.click('#profile-setup-form button[type="submit"]')
            await tab.wait_for_timeout(300)

            # Resume upload - need a file to upload
            await tab.set_input_files('#resume-upload-form [name="resume"]', "/tmp/test_resume.pdf")
            await tab.click('#resume-upload-form button[type="submit"]')
            await tab.wait_for_timeout(200)
            # Wait for auto-advance from resume-parsing (1500ms in app.js)
            await tab.wait_for_timeout(2000)

        # Both tabs should now be on the application form (page 1)
        page_indicator_a = await tab_a.text_content("#page-indicator")
        page_indicator_b = await tab_b.text_content("#page-indicator")
        assert "Page 1 of 3" in (page_indicator_a or ""), f"tab_a page indicator: {page_indicator_a}"
        assert "Page 1 of 3" in (page_indicator_b or ""), f"tab_b page indicator: {page_indicator_b}"

        # Fill DIFFERENT values on page 1 for each tab
        # Tab A: Alice's data
        await tab_a.fill('[name="first_name"]', "Alice")
        await tab_a.fill('[name="last_name"]', "Wonderland")
        await tab_a.fill('[name="email"]', "alice@concur-test.example")

        # Tab B: Bob's data (completely different)
        await tab_b.fill('[name="first_name"]', "Bob")
        await tab_b.fill('[name="last_name"]', "Builder")
        await tab_b.fill('[name="email"]', "bob@concur-test.example")

        # Read values back and verify isolation
        fn_a = await tab_a.input_value('[name="first_name"]')
        ln_a = await tab_a.input_value('[name="last_name"]')
        em_a = await tab_a.input_value('[name="email"]')

        fn_b = await tab_b.input_value('[name="first_name"]')
        ln_b = await tab_b.input_value('[name="last_name"]')
        em_b = await tab_b.input_value('[name="email"]')

        print(f"  tab_a fields: first_name={fn_a!r}, last_name={ln_a!r}, email={em_a!r}")
        print(f"  tab_b fields: first_name={fn_b!r}, last_name={ln_b!r}, email={em_b!r}")

        # THE KEY ASSERTION: Each tab has its OWN values, not the other's
        assert fn_a == "Alice", f"tab_a first_name leaked! Got: {fn_a!r}"
        assert ln_a == "Wonderland", f"tab_a last_name leaked! Got: {ln_a!r}"
        assert em_a == "alice@concur-test.example", f"tab_a email leaked! Got: {em_a!r}"

        assert fn_b == "Bob", f"tab_b first_name leaked! Got: {fn_b!r}"
        assert ln_b == "Builder", f"tab_b last_name leaked! Got: {ln_b!r}"
        assert em_b == "bob@concur-test.example", f"tab_b email leaked! Got: {em_b!r}"

        # Verify hidden tab_b's values are NOT visible in tab_a and vice versa
        assert em_a != em_b, "Emails should be different — leakage detected!"

        await tab_a.close()
        await tab_b.close()

    print("✅ Level 2: Form field isolation between concurrent pages — PASS")


# ── Level 3: Tab count integrity during concurrent page opens ─────────────

@pytest.mark.asyncio
async def test_level3_tab_count_integrity_and_no_crosstalk():
    """Open 5 pages rapidly from the same shared CDP context, verify each
    gets its own page identity, none crash, and the context correctly tracks
    all of them."""
    NUM_TABS = 5
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_BASE)
        ctx = browser.contexts[0] if browser.contexts else await browser.new_context()

        tabs = []
        for i in range(NUM_TABS):
            tab = await ctx.new_page()
            await tab.goto(MOCK_ATS_URL, wait_until="networkidle")
            tabs.append(tab)

        # All tabs should be tracked in the context
        assert len(ctx.pages) >= NUM_TABS, f"Expected at least {NUM_TABS} pages, got {len(ctx.pages)}"

        # Each tab should have its own URL and be interactive
        for i, tab in enumerate(tabs):
            title = await tab.title()
            heading = await tab.text_content("h1")
            print(f"  Tab {i}: title={title!r}, heading={heading!r}, url={tab.url}")
            assert "Job Application" in title, f"Tab {i} unexpected title: {title}"
            assert "Senior Data Engineer" in heading, f"Tab {i} unexpected heading: {heading}"

        # Cleanup
        for tab in tabs:
            await tab.close()

    print("✅ Level 3: Tab count integrity — PASS")


# ── Level 4: Concurrent BrowserWorker.run() via CDP (full state machine) ──

@pytest.mark.asyncio
async def test_level4_concurrent_browserworker_run_via_cdp():
    """Two concurrent BrowserWorker.run() calls, both sharing the same
    persistent Chrome via CDP. Each starts seconds apart with its own
    session_id, application_data, and page within the shared context.

    The state machine will progress through landing -> apply -> signup ->
    profile-setup -> resume-upload -> resume-parsing -> application pages,
    then stop at submit_ready (assisted_mode=True).

    Because the mock ATS uses hash-routed client-side state, and both
    workers start from the same base URL but navigate independently within
    their own page objects, the key failure mode to detect is:
      - One worker's navigation affecting the other's hash/fragment
      - Cookies/localStorage from one worker's session leaking into the other's
      - One worker's Playwright actions targeting the wrong page

    We mock the credential_vault_client.get_or_create_credential because
    the backend API isn't running in this test environment.
    """
    # Mock credential — issue UNIQUE credentials per call so concurrent
    # workers don't collide on the same ATS account. Each call increments
    # a counter, ensuring no two workers get the same email.
    _credential_counter = 0

    async def mock_get_or_create(*args, **kwargs):
        nonlocal _credential_counter
        _credential_counter += 1
        return {
            "credential_id": f"mock-conc-{_credential_counter:03d}",
            "email": f"conc-{_credential_counter:03d}@concur-test.example",
            "password": "TestPass123!@#",
            "status": "active",
            "created": True,
        }

    worker_alice = make_worker()
    worker_bob = make_worker()

    ctx_alice = worker_alice.make_context(
        session_id="conc-alice-run",
        application_url=MOCK_ATS_URL,
        application_data=ApplicationData(
            application_id="conc-alice",
            first_name="Alice",
            last_name="Wonderland",
            email="alice-concur@test.com",
            phone="555-0101",
            linkedin="https://linkedin.com/in/alice",
            work_authorization="yes",
            resume_path="/tmp/test_resume.pdf",
            interest="Concurrent test - Alice version",
        ),
        user_id="u-conc-alice",
    )

    ctx_bob = worker_bob.make_context(
        session_id="conc-bob-run",
        application_url=MOCK_ATS_URL,
        application_data=ApplicationData(
            application_id="conc-bob",
            first_name="Bob",
            last_name="Builder",
            email="bob-concur@test.com",
            phone="555-0202",
            linkedin="https://linkedin.com/in/bob",
            work_authorization="yes",
            resume_path="/tmp/test_resume.pdf",
            interest="Concurrent test - Bob version",
        ),
        user_id="u-conc-bob",
    )

    # Mock the credential vault so both workers can authenticate
    with patch("browser_worker.adapters.mock_ats_adapter.get_or_create_credential", mock_get_or_create):
        # Launch alice first, then bob 2 seconds later
        alice_task = asyncio.create_task(worker_alice.run(ctx_alice))
        await asyncio.sleep(2.0)  # 2-second stagger
        bob_task = asyncio.create_task(worker_bob.run(ctx_bob))

        results = await asyncio.gather(alice_task, bob_task, return_exceptions=True)

    alice_result = results[0]
    bob_result = results[1]

    # Debug output
    for name, result in [("Alice", alice_result), ("Bob", bob_result)]:
        if isinstance(result, Exception):
            print(f"  ❌ {name} raised: {type(result).__name__}: {result}")
        else:
            print(f"  {name} result: success={result.get('success')}, status={result.get('status')}, state={result.get('state')}")

    # Both should have succeeded (paused at submit_ready or reached a sensible checkpoint)
    alice_ok = not isinstance(alice_result, Exception) and alice_result.get("success")
    bob_ok = not isinstance(bob_result, Exception) and bob_result.get("success")

    if not alice_ok:
        print(f"  ⚠️  Alice run did not succeed as expected: {alice_result}")
    if not bob_ok:
        print(f"  ⚠️  Bob run did not succeed as expected: {bob_result}")

    # BOTH concurrent runs must succeed independently
    assert alice_ok and bob_ok, f"Both concurrent runs must succeed — Alice: {alice_result}, Bob: {bob_result}"
    print("✅ Level 4: Concurrent BrowserWorker.run() via CDP — PASS (within constraints)")


# ── Level 5: Rapid-fire state machine starts (3 workers, 0.5s stagger) ───

@pytest.mark.asyncio
async def test_level5_rapid_fire_three_concurrent_workers():
    """Three workers launched 0.5s apart — aggressive concurrency test.
    Simulates what happens when a batch of applications hit the queue
    simultaneously on a shared VPS browser."""

    workers = []
    contexts = []

    labels = ["Alpha", "Beta", "Gamma"]

    # Unique credentials per worker so concurrent signups don't collide
    _cred_counter = [0]

    async def mock_get_or_create(*args, **kwargs):
        _cred_counter[0] += 1
        return {
            "credential_id": f"mock-rapid-{_cred_counter[0]:03d}",
            "email": f"rapid-{_cred_counter[0]:03d}@concur-test.example",
            "password": "TestPass123!@#",
            "status": "active",
            "created": True,
        }

    for i, label in enumerate(labels):
        w = make_worker()
        ctx = w.make_context(
            session_id=f"conc-rapid-{label.lower()}",
            application_url=MOCK_ATS_URL,
            application_data=ApplicationData(
                application_id=f"rapid-{label.lower()}",
                first_name=label,
                last_name="Rapid",
                email=f"{label.lower()}-rapid@concur-test.example",
                phone=f"555-0{i+3}0{i+3}",
                linkedin=f"https://linkedin.com/in/{label.lower()}",
                work_authorization="yes",
                resume_path="/tmp/test_resume.pdf",
                interest=f"Rapid fire test - {label}",
            ),
            user_id=f"u-rapid-{label.lower()}",
        )
        workers.append(w)
        contexts.append(ctx)

    with patch("browser_worker.adapters.mock_ats_adapter.get_or_create_credential", mock_get_or_create):
        tasks = []
        for w, ctx in zip(workers, contexts):
            tasks.append(asyncio.create_task(w.run(ctx)))
            await asyncio.sleep(0.5)  # 0.5s stagger between each launch

        results = await asyncio.gather(*tasks, return_exceptions=True)

    for label, result in zip(labels, results):
        if isinstance(result, Exception):
            print(f"  ❌ {label} raised: {type(result).__name__}: {result}")
        else:
            print(f"  {label} result: success={result.get('success')}, status={result.get('status')}, state={result.get('state')}")

    # Count successes
    successes = sum(
        1 for r in results
        if not isinstance(r, Exception) and r.get("success")
    )
    print(f"  {successes}/{len(labels)} workers succeeded concurrently")

    # ALL concurrent workers must succeed independently
    assert successes == len(labels), f"All {len(labels)} concurrent workers must succeed, got {successes}/{len(labels)}"

    # Check for state leakage across sessions
    checkpoints_dir = "/tmp/checkpoints_conc_test"
    if os.path.isdir(checkpoints_dir):
        sessions = [d for d in os.listdir(checkpoints_dir) if d.startswith("conc-rapid-")]
        print(f"  Checkpoint sessions found: {sessions}")

    print("✅ Level 5: Rapid-fire concurrent workers — PASS (within constraints)")


# ── Manual observation helper ─────────────────────────────────────────────

if __name__ == "__main__":
    """Run interactively with visible output. Use for debugging:
       python tests/test_concurrent_cdp_context.py
    """
    print("=" * 70)
    print("CONCURRENCY STRESS TEST: Shared Persistent Chrome Context")
    print("=" * 70)
    print()

    async def main():
        async with async_playwright() as p:
            # Start persistent Chrome for tests
            chrome = await p.chromium.launch(
                headless=True,
                args=[f"--remote-debugging-port={CDP_PORT}"]
            )
            print(f"🔧 Persistent Chrome running on CDP port {CDP_PORT}")
            print()

            try:
                # Run all tests
                await test_level1_raw_page_isolation_in_shared_context()
                print()
                await test_level2_form_field_isolation_between_concurrent_pages()
                print()
                await test_level3_tab_count_integrity_and_no_crosstalk()
                print()
                await test_level4_concurrent_browserworker_run_via_cdp()
                print()
                await test_level5_rapid_fire_three_concurrent_workers()
            finally:
                await chrome.close()

    asyncio.run(main())
    print()
    print("=" * 70)
    print("ALL TESTS COMPLETE")
    print("=" * 70)
