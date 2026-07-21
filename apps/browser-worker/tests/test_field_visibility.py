"""Tests for is_genuinely_fillable's honeypot-vs-legitimate-widget signal.

Uses page.set_content with markup shaped directly from real-ATS research
(Workday's beecatcher honeypot, Ashby's near-invisible file input, Lever's
progressively-disclosed EEO follow-up field, vendor CAPTCHA response
fields) rather than the shared mock-ats fixture, since these are pure DOM-
shape checks with no dependency on the multi-stage application flow.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.services.field_visibility import is_genuinely_fillable


# Chromium's UA stylesheet gives text/select controls default border+padding
# that inflates the rendered box well past an inline width/height:0 - real
# ATS platforms only achieve true near-zero geometry because their global
# CSS reset already zeroes this out (confirmed in the live Workday research:
# the actual beecatcher field measured 1x0.01px). Reproduce that reset here
# so these snippets measure the same way production markup does.
_RESET_CSS = "<style>input,select,textarea{border:none;padding:0;margin:0;box-sizing:border-box;}</style>"


async def _fillable_for(html: str, selector: str) -> bool:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(f"<body>{_RESET_CSS}{html}</body>")
        el = await page.query_selector(selector)
        result = await is_genuinely_fillable(el)
        await browser.close()
        return result


class TestHoneypotExclusion:
    @pytest.mark.asyncio
    async def test_workday_style_beecatcher_is_excluded(self):
        html = """
        <input type="text" name="website" data-automation-id="beecatcher"
               tabindex="-1" autocomplete="off"
               style="width:1px; height:0.01px; overflow:hidden; position:absolute; opacity:1;">
        """
        assert await _fillable_for(html, "[name='website']") is False

    @pytest.mark.asyncio
    async def test_near_zero_field_with_no_label_is_excluded(self):
        html = '<input type="text" name="mystery" style="width:0; height:0;">'
        assert await _fillable_for(html, "[name='mystery']") is False


class TestLegitimateNearZeroFieldsAreKept:
    @pytest.mark.asyncio
    async def test_file_input_behind_custom_button_is_kept(self):
        """Ashby renders resume upload as a 1x1 native <input type=file>
        behind a styled 'Upload file' button - never a honeypot pattern."""
        html = """
        <button type="button">Upload file</button>
        <input type="file" name="resume" style="width:1px; height:1px;">
        """
        assert await _fillable_for(html, "[name='resume']") is True

    @pytest.mark.asyncio
    async def test_near_zero_field_with_label_for_is_kept(self):
        html = """
        <label for="gender-select">Gender</label>
        <select id="gender-select" name="gender" style="width:1px; height:1px; overflow:hidden;">
            <option value="f">Female</option>
        </select>
        """
        assert await _fillable_for(html, "#gender-select") is True

    @pytest.mark.asyncio
    async def test_near_zero_field_with_aria_label_is_kept(self):
        html = '<input type="text" name="country_code" aria-label="Country code" style="width:0; height:0;">'
        assert await _fillable_for(html, "[name='country_code']") is True

    @pytest.mark.asyncio
    async def test_near_zero_field_wrapped_in_label_is_kept(self):
        html = """
        <label style="width:0; height:0; overflow:hidden; display:block;">
            Marketing opt-in
            <input type="checkbox" name="marketing_optin">
        </label>
        """
        assert await _fillable_for(html, "[name='marketing_optin']") is True


class TestCaptchaResponseFieldsExcluded:
    @pytest.mark.asyncio
    async def test_recaptcha_response_field_excluded_even_with_label(self):
        """g-recaptcha-response is populated by vendor JS, never applicant
        data - excluded categorically regardless of label presence."""
        html = """
        <label for="g-recaptcha-response">reCAPTCHA</label>
        <textarea id="g-recaptcha-response" name="g-recaptcha-response" style="width:0; height:0;"></textarea>
        """
        assert await _fillable_for(html, "#g-recaptcha-response") is False

    @pytest.mark.asyncio
    async def test_hcaptcha_response_field_excluded(self):
        html = '<input type="hidden" name="h-captcha-response" id="hcaptchaResponseInput" style="width:0;height:0;">'
        # type=hidden is out of scope for this check upstream in real callers,
        # but the function itself should still exclude it defensively.
        assert await _fillable_for(html, "#hcaptchaResponseInput") is False


class TestConditionallyRevealedFieldsAreLeftAlone:
    @pytest.mark.asyncio
    async def test_progressive_disclosure_field_not_yet_revealed_is_excluded(self):
        """Lever's eeo[disabilitySignature] is 0x0 with no label until the
        disability question is answered - correctly skipped this pass, will
        be picked up naturally once revealed with real geometry/label."""
        html = '<input type="text" name="eeo[disabilitySignature]" style="width:0; height:0;">'
        assert await _fillable_for(html, "[name='eeo[disabilitySignature]']") is False
