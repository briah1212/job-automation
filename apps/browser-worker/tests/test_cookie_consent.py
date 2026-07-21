"""Tests for dismiss_cookie_consent - prefers reject/decline over accept.

The Lever banner button labels ("Deny"/"Accept") found during live research
are used directly as the primary case.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.services.cookie_consent import dismiss_cookie_consent


async def _run_against(html: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(f"<body>{html}</body>")
        dismissed = await dismiss_cookie_consent(page)
        # Report which buttons, if any, are still visible afterwards so
        # callers can assert on click choice without a JS callback wiring.
        remaining = await page.eval_on_selector_all(
            "button", "els => els.filter(e => e.offsetParent !== null).map(e => e.textContent.trim())"
        )
        await browser.close()
        return dismissed, remaining


class TestPrefersReject:
    @pytest.mark.asyncio
    async def test_lever_style_deny_accept_clicks_deny(self):
        html = """
        <div id="banner">
            <button onclick="document.getElementById('banner').remove()">Deny</button>
            <button>Accept</button>
        </div>
        """
        dismissed, remaining = await _run_against(html)
        assert dismissed is True
        assert remaining == []

    @pytest.mark.asyncio
    async def test_reject_all_preferred_over_accept_all(self):
        html = """
        <div id="banner">
            <button>Accept All</button>
            <button onclick="document.getElementById('banner').remove()">Reject All</button>
        </div>
        """
        dismissed, remaining = await _run_against(html)
        assert dismissed is True
        assert remaining == []


class TestFallsBackToAccept:
    @pytest.mark.asyncio
    async def test_accept_only_banner_is_dismissed(self):
        html = '<button onclick="this.remove()">Accept All Cookies</button>'
        dismissed, remaining = await _run_against(html)
        assert dismissed is True
        assert remaining == []


class TestNoOpWhenNoBanner:
    @pytest.mark.asyncio
    async def test_unrelated_buttons_left_alone(self):
        html = '<button>Apply Now</button>'
        dismissed, remaining = await _run_against(html)
        assert dismissed is False
        assert remaining == ["Apply Now"]
