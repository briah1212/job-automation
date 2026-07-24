"""Tests for detect_captcha_challenge - vendor-agnostic, visible-challenge-only.

Markup shapes drawn from live research: Greenhouse/Ashby use reCAPTCHA,
Lever uses hCaptcha. Also verifies the deliberate non-trigger on invisible
reCAPTCHA v3, which injects a `g-recaptcha-response` field and a small badge
on essentially every page load without ever presenting a challenge - a
naive "field present" check would pause on nearly every Greenhouse/Ashby
application regardless of whether a human was ever needed.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.services.captcha_detection import detect_captcha_challenge


async def _detected_for(html: str) -> bool:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(f"<body>{html}</body>")
        result = await detect_captcha_challenge(page)
        await browser.close()
        return result


class TestInteractiveChallengesDetected:
    """Container divs get an explicit size matching the real rendered widget
    (e.g. reCAPTCHA v2's checkbox is ~304x78px) - an empty <div> with no
    content collapses to 0 height by default, which is not how these look
    once the vendor's script actually populates them on a live page."""

    @pytest.mark.asyncio
    async def test_recaptcha_v2_checkbox_container_detected(self):
        html = '<div class="g-recaptcha" data-sitekey="abc123" style="width:304px;height:78px;"></div>'
        assert await _detected_for(html) is True

    @pytest.mark.asyncio
    async def test_hcaptcha_container_detected(self):
        html = '<div class="h-captcha" data-sitekey="abc123" style="width:303px;height:78px;"></div>'
        assert await _detected_for(html) is True

    @pytest.mark.asyncio
    async def test_recaptcha_anchor_iframe_detected(self):
        html = '<iframe title="reCAPTCHA" src="about:blank"></iframe>'
        assert await _detected_for(html) is True

    @pytest.mark.asyncio
    async def test_recaptcha_v2_checkbox_size_normal_detected(self):
        """Confirmed live against a real BambooHR posting: the genuine
        interactive checkbox's own src URL contains `size=normal` (and
        the widget renders at 304x78px) - this is the shape that must
        keep triggering detection even after excluding size=invisible
        below."""
        html = (
            '<iframe title="reCAPTCHA" style="width:304px;height:78px;" '
            'src="https://www.google.com/recaptcha/api2/anchor?size=normal&k=abc123"></iframe>'
        )
        assert await _detected_for(html) is True

    @pytest.mark.asyncio
    async def test_cloudflare_turnstile_detected(self):
        html = '<div class="cf-turnstile" data-sitekey="abc123" style="width:300px;height:65px;"></div>'
        assert await _detected_for(html) is True

    @pytest.mark.asyncio
    async def test_datadome_block_page_detected(self):
        """Confirmed live against a real SmartRecruiters (WesternDigital)
        posting: DataDome's block shell replaces the entire page body with
        exactly this markup - a #cmsg placeholder plus a script pulled
        from captcha-delivery.com."""
        html = '<p id="cmsg">Please enable JS and disable any ad blocker</p><script src="https://ct.captcha-delivery.com/c.js"></script>'
        assert await _detected_for(html) is True


class TestInvisibleV3NotTriggered:
    @pytest.mark.asyncio
    async def test_hidden_response_field_alone_not_detected(self):
        """Invisible reCAPTCHA v3 injects only this field (populated by JS
        that runs silently in the background) - present on nearly every
        Greenhouse/Ashby page regardless of whether a challenge ever fires."""
        html = '<textarea id="g-recaptcha-response" name="g-recaptcha-response" style="display:none;"></textarea>'
        assert await _detected_for(html) is False

    @pytest.mark.asyncio
    async def test_no_captcha_markup_not_detected(self):
        html = '<form><input type="text" name="first_name"></form>'
        assert await _detected_for(html) is False

    @pytest.mark.asyncio
    async def test_display_none_container_not_detected(self):
        html = '<div class="g-recaptcha" data-sitekey="abc123" style="display:none;"></div>'
        assert await _detected_for(html) is False

    @pytest.mark.asyncio
    async def test_recaptcha_v3_invisible_badge_not_detected(self):
        """CRITICAL, confirmed live against a real Jobvite posting
        (NinjaOne): its candidate application form legitimately embeds
        this exact badge (title='reCAPTCHA', 256x60px, src containing
        size=invisible) - it scores traffic silently and never presents a
        challenge to a real user, yet the old selector (`iframe[title=
        'reCAPTCHA']:visible` with no further distinction) matched it
        anyway, since a 256x60 iframe genuinely IS Playwright-:visible -
        "invisible" is reCAPTCHA's own vocabulary for "never presents an
        interactive challenge," not "has zero CSS size." Wrongly paused
        an application that had no real CAPTCHA blocking it at all."""
        html = (
            '<iframe title="reCAPTCHA" style="width:256px;height:60px;" '
            'src="https://www.recaptcha.net/recaptcha/api2/anchor?size=invisible&k=abc123"></iframe>'
        )
        assert await _detected_for(html) is False
