"""Live tests against the mock-ats fixture (requires MOCK_ATS_URL reachable,
default http://mock-ats:8080 inside docker-compose, http://localhost:8080
when run on the host). Replaces the pre-state-machine test_adapters.py, which
referenced BrowserWorker.process_application/resume_from_checkpoint (removed
in the Phase 3 refactor) and assumed the old single-stage fixture layout
(resume upload on application page 2, no landing/auth/profile-setup flow).
"""
import os
import tempfile
import uuid

import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters import MockATSAdapter
from browser_worker.state import BrowserState

MOCK_ATS_URL = os.environ.get("MOCK_ATS_URL", "http://mock-ats:8080")

# mock-ats's account store is a real, process-lifetime dict on a long-lived
# docker-compose service (never restarted between test runs) - a fixed
# email here would 409-collide with whatever an earlier run already
# registered, silently failing signup and cascading into "element not
# visible" timeouts several steps later. See test_generic_adapter_detect_state.py's
# _run_id for the same fix applied there (root cause of this suite's
# "passes alone, fails together" flakiness).
_RUN_ID = uuid.uuid4().hex[:12]


@pytest.fixture
async def mock_ats_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(MOCK_ATS_URL, wait_until="networkidle")
        yield page
        await browser.close()


class TestDetect:
    @pytest.mark.asyncio
    async def test_detect_mock_ats(self, mock_ats_page):
        adapter = MockATSAdapter()
        assert await adapter.detect(mock_ats_page) is True


class TestDetectState:
    @pytest.mark.asyncio
    async def test_landing(self, mock_ats_page):
        adapter = MockATSAdapter()
        state, confidence = await adapter.detect_state(mock_ats_page)
        assert state == BrowserState.LANDING
        assert confidence == 1.0

    @pytest.mark.asyncio
    async def test_apply(self, mock_ats_page):
        adapter = MockATSAdapter()
        await mock_ats_page.click("#apply-btn")
        state, _ = await adapter.detect_state(mock_ats_page)
        assert state == BrowserState.APPLY

    @pytest.mark.asyncio
    async def test_signup(self, mock_ats_page):
        adapter = MockATSAdapter()
        await mock_ats_page.click("#apply-btn")
        await mock_ats_page.click("#show-signup-btn")
        state, _ = await adapter.detect_state(mock_ats_page)
        assert state == BrowserState.CREATE_ACCOUNT

    @pytest.mark.asyncio
    async def test_login(self, mock_ats_page):
        adapter = MockATSAdapter()
        await mock_ats_page.click("#apply-btn")
        await mock_ats_page.click("#show-login-btn")
        state, _ = await adapter.detect_state(mock_ats_page)
        assert state == BrowserState.LOGIN

    @pytest.mark.asyncio
    async def test_email_verification_dead_end(self, mock_ats_page):
        """A signup email containing "verify" is a deliberate deterministic
        test hook (see fixtures/ats-sites/mock-ats/app.js) - it must never
        try to resolve via inbox automation, only ever escalate."""
        adapter = MockATSAdapter()
        await mock_ats_page.click("#apply-btn")
        await mock_ats_page.click("#show-signup-btn")
        await mock_ats_page.fill('[name="signup_email"]', "verify-test@example.com")
        await mock_ats_page.fill('[name="signup_password"]', "Sup3rSecure!Pass")
        await mock_ats_page.fill('[name="signup_confirm_password"]', "Sup3rSecure!Pass")
        await mock_ats_page.click('#signup-form button[type="submit"]')
        await mock_ats_page.wait_for_timeout(800)
        state, _ = await adapter.detect_state(mock_ats_page)
        assert state == BrowserState.EMAIL_VERIFICATION


class TestInspectForm:
    @pytest.mark.asyncio
    async def test_inspect_application_page1(self, mock_ats_page):
        adapter = MockATSAdapter()
        # Navigate through the real flow to reach the application form - the
        # mock ATS's "pages" are hash-routed stages, not directly linkable.
        await mock_ats_page.click("#apply-btn")
        await mock_ats_page.click("#show-signup-btn")
        await mock_ats_page.fill('[name="signup_email"]', f"inspecttest-{_RUN_ID}@example.com")
        await mock_ats_page.fill('[name="signup_password"]', "Sup3rSecure!Pass")
        await mock_ats_page.fill('[name="signup_confirm_password"]', "Sup3rSecure!Pass")
        await mock_ats_page.click('#signup-form button[type="submit"]')
        await mock_ats_page.wait_for_timeout(800)
        await mock_ats_page.select_option('[name="referral_source"]', "job_board")
        await mock_ats_page.click('#profile-setup-form button[type="submit"]')
        await mock_ats_page.wait_for_timeout(800)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4\n%%EOF")
            resume_path = f.name
        await mock_ats_page.set_input_files('#resume-upload-form [name="resume"]', resume_path)
        await mock_ats_page.click('#resume-upload-form button[type="submit"]')
        await mock_ats_page.wait_for_timeout(2000)  # resume-parsing auto-advance

        form = await adapter.inspect_form(mock_ats_page)
        assert form.page_number == 1
        assert form.total_pages == 3
        field_names = [f.name for f in form.fields]
        assert "first_name" in field_names
        assert "last_name" in field_names
        assert "email" in field_names
        # resume upload happens earlier now, page 1 must not have a file field
        assert "resume" not in field_names
        # Honeypot (no associated label, near-zero geometry) must be excluded -
        # see services/field_visibility.py and the Workday "beecatcher" finding.
        assert "website" not in field_names
        # A legitimate near-zero-size field WITH a real <label for> must still
        # be picked up - mirrors Greenhouse/Ashby's custom-styled widgets.
        assert "pronouns" in field_names


class TestFillFieldAndNavigate:
    @pytest.mark.asyncio
    async def test_navigate_next_scopes_to_visible_page(self, mock_ats_page):
        """Regression test for the DOM-scoping bug found this session:
        navigate_next used to grab page 1's (hidden) next-btn regardless of
        which page was actually visible."""
        adapter = MockATSAdapter()
        await mock_ats_page.click("#apply-btn")
        await mock_ats_page.click("#show-signup-btn")
        await mock_ats_page.fill('[name="signup_email"]', f"navtest-{_RUN_ID}@example.com")
        await mock_ats_page.fill('[name="signup_password"]', "Sup3rSecure!Pass")
        await mock_ats_page.fill('[name="signup_confirm_password"]', "Sup3rSecure!Pass")
        await mock_ats_page.click('#signup-form button[type="submit"]')
        await mock_ats_page.wait_for_timeout(800)
        await mock_ats_page.select_option('[name="referral_source"]', "job_board")
        await mock_ats_page.click('#profile-setup-form button[type="submit"]')
        await mock_ats_page.wait_for_timeout(800)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4\n%%EOF")
            resume_path = f.name
        await mock_ats_page.set_input_files('#resume-upload-form [name="resume"]', resume_path)
        await mock_ats_page.click('#resume-upload-form button[type="submit"]')
        await mock_ats_page.wait_for_timeout(2000)

        await mock_ats_page.fill('[name="first_name"]', "Nav")
        await mock_ats_page.fill('[name="last_name"]', "Test")
        await mock_ats_page.fill('[name="email"]', f"navtest-{_RUN_ID}@example.com")

        result = await adapter.navigate_next(mock_ats_page)
        assert result.success is True
        assert result.page_number == 2

        # Page 2's fields must now be the ones actually reachable/visible.
        await mock_ats_page.select_option('[name="work_authorization"]', "yes")
        await mock_ats_page.select_option('[name="willing_to_relocate"]', "yes")
        result2 = await adapter.navigate_next(mock_ats_page)
        assert result2.success is True
        assert result2.page_number == 3


class TestGenericAdapterDetect:
    @pytest.mark.asyncio
    async def test_generic_adapter_always_detects(self):
        from browser_worker.adapters import GenericAdapter

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content("<html><body><form></form></body></html>")
            assert await GenericAdapter().detect(page) is True
            await browser.close()
