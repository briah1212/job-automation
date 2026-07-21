"""GenericAdapter.detect_state must correctly classify every BrowserState
using only generic signals (URL substrings, headings, button text,
password/file field presence, unchecked-required-checkbox) - no fixture-
specific selectors. Verified live against the mock-ats fixture as the
reference implementation of a real (if simple) multi-page, multi-stage ATS.
"""
import itertools
import os
import pathlib
import tempfile

import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import GenericAdapter
from browser_worker.state import BrowserState

MOCK_ATS_URL = os.environ.get("MOCK_ATS_URL", "http://mock-ats:8080")

# server.py's account store is a real, process-lifetime dict (deliberately -
# it's what makes credential-reuse actually testable) - a second signup
# attempt with an already-used email correctly gets rejected as a duplicate
# account, so every test that signs up needs its own unique email.
_email_counter = itertools.count()


def _unique_email(label: str) -> str:
    return f"{label}-{next(_email_counter)}@example.com"


@pytest.fixture
async def pw_browser():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        yield b
        await b.close()


async def _new_page(pw_browser):
    page = await pw_browser.new_page()
    await page.goto(MOCK_ATS_URL, wait_until="networkidle")
    return page


class TestGenericDetectStatePreApplication:
    @pytest.mark.asyncio
    async def test_landing(self, pw_browser):
        page = await _new_page(pw_browser)
        state, confidence = await GenericAdapter().detect_state(page)
        assert state == BrowserState.LANDING
        assert confidence >= 0.5

    @pytest.mark.asyncio
    async def test_apply(self, pw_browser):
        page = await _new_page(pw_browser)
        await page.click("#apply-btn")
        await page.wait_for_timeout(200)
        state, _ = await GenericAdapter().detect_state(page)
        assert state == BrowserState.APPLY

    @pytest.mark.asyncio
    async def test_login(self, pw_browser):
        page = await _new_page(pw_browser)
        await page.click("#apply-btn")
        await page.click("#show-login-btn")
        await page.wait_for_timeout(200)
        state, _ = await GenericAdapter().detect_state(page)
        assert state == BrowserState.LOGIN

    @pytest.mark.asyncio
    async def test_create_account(self, pw_browser):
        page = await _new_page(pw_browser)
        await page.click("#apply-btn")
        await page.click("#show-signup-btn")
        await page.wait_for_timeout(200)
        state, _ = await GenericAdapter().detect_state(page)
        assert state == BrowserState.CREATE_ACCOUNT

    @pytest.mark.asyncio
    async def test_email_verification(self, pw_browser):
        page = await _new_page(pw_browser)
        await page.click("#apply-btn")
        await page.click("#show-signup-btn")
        await page.fill('[name="signup_email"]', _unique_email("verify-generic"))
        await page.fill('[name="signup_password"]', "Sup3rSecure!Pass")
        await page.fill('[name="signup_confirm_password"]', "Sup3rSecure!Pass")
        await page.click('#signup-form button[type="submit"]')
        await page.wait_for_timeout(800)
        state, _ = await GenericAdapter().detect_state(page)
        assert state == BrowserState.EMAIL_VERIFICATION

    @pytest.mark.asyncio
    async def test_profile_setup(self, pw_browser):
        page = await _new_page(pw_browser)
        await page.click("#apply-btn")
        await page.click("#show-signup-btn")
        await page.fill('[name="signup_email"]', _unique_email("genprofile"))
        await page.fill('[name="signup_password"]', "Sup3rSecure!Pass")
        await page.fill('[name="signup_confirm_password"]', "Sup3rSecure!Pass")
        await page.click('#signup-form button[type="submit"]')
        await page.wait_for_timeout(800)
        state, _ = await GenericAdapter().detect_state(page)
        assert state == BrowserState.PROFILE_SETUP

    @pytest.mark.asyncio
    async def test_resume_upload(self, pw_browser):
        page = await _new_page(pw_browser)
        await page.click("#apply-btn")
        await page.click("#show-signup-btn")
        await page.fill('[name="signup_email"]', _unique_email("genresume"))
        await page.fill('[name="signup_password"]', "Sup3rSecure!Pass")
        await page.fill('[name="signup_confirm_password"]', "Sup3rSecure!Pass")
        await page.click('#signup-form button[type="submit"]')
        await page.wait_for_timeout(800)
        await page.select_option('[name="referral_source"]', "job_board")
        await page.click('#profile-setup-form button[type="submit"]')
        await page.wait_for_timeout(800)
        state, _ = await GenericAdapter().detect_state(page)
        assert state == BrowserState.RESUME_UPLOAD


class TestGenericDetectStateApplicationFlow:
    @pytest.fixture
    async def page_at_application(self, pw_browser):
        page = await _new_page(pw_browser)
        email = _unique_email("genflow")
        await page.click("#apply-btn")
        await page.click("#show-signup-btn")
        await page.fill('[name="signup_email"]', email)
        await page.fill('[name="signup_password"]', "Sup3rSecure!Pass")
        await page.fill('[name="signup_confirm_password"]', "Sup3rSecure!Pass")
        await page.click('#signup-form button[type="submit"]')
        await page.wait_for_timeout(800)
        await page.select_option('[name="referral_source"]', "job_board")
        await page.click('#profile-setup-form button[type="submit"]')
        await page.wait_for_timeout(800)

        tmp_pdf = pathlib.Path(tempfile.mktemp(suffix=".pdf"))
        tmp_pdf.write_bytes(b"%PDF-1.4\n%%EOF")
        await page.set_input_files('#resume-upload-form [name="resume"]', str(tmp_pdf))
        await page.click('#resume-upload-form button[type="submit"]')
        await page.wait_for_timeout(2000)
        return page, email

    @pytest.mark.asyncio
    async def test_resume_parse_wait_or_application(self, page_at_application):
        """The parse-wait auto-advance can land either state depending on timing."""
        page, _email = page_at_application
        state, _ = await GenericAdapter().detect_state(page)
        assert state in (BrowserState.RESUME_PARSE_WAIT, BrowserState.APPLICATION)

    @pytest.mark.asyncio
    async def test_application(self, page_at_application):
        page, email = page_at_application
        state, _ = await GenericAdapter().detect_state(page)
        assert state == BrowserState.APPLICATION

        await page.fill('[name="first_name"]', "Generic")
        await page.fill('[name="last_name"]', "Test")
        await page.fill('[name="email"]', email)
        await page.click(".form-page[data-page='1'] button.next-btn")
        await page.wait_for_timeout(800)
        state2, _ = await GenericAdapter().detect_state(page)
        assert state2 == BrowserState.APPLICATION

    @pytest.mark.asyncio
    async def test_review_then_submit_ready(self, page_at_application):
        page, email = page_at_application
        await page.fill('[name="first_name"]', "Generic")
        await page.fill('[name="last_name"]', "Test")
        await page.fill('[name="email"]', email)
        await page.click(".form-page[data-page='1'] button.next-btn")
        await page.wait_for_timeout(800)
        await page.select_option('[name="work_authorization"]', "yes")
        await page.select_option('[name="willing_to_relocate"]', "yes")
        await page.click(".form-page[data-page='2'] button.next-btn")
        await page.wait_for_timeout(800)

        state, _ = await GenericAdapter().detect_state(page)
        assert state == BrowserState.REVIEW

        await page.check('[name="terms"]')
        state2, _ = await GenericAdapter().detect_state(page)
        assert state2 == BrowserState.SUBMIT_READY
