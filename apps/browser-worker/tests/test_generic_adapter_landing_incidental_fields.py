"""Regression test: _score_landing's incidental-fields penalty must only
apply when the Apply CTA is a same-page reveal, not a genuine navigation.

Found live testing a real Duke University (SuccessFactors) posting: an
ordinary job-description landing page has a handful of unrelated
incidental fields (a site-wide "Search by Keyword" box, a job-alert-
subscription widget) that have nothing to do with the application, while
its real "Apply now" link points to a genuinely different URL
(/talentcommunity/apply/...). The penalty this test covers was added
earlier (see git history) for a real Greenhouse posting whose Apply CTA
is a same-page anchor/JS scroll to an already-rendered form - a
meaningfully different shape. Without distinguishing them, Duke's landing
page scored too low (0.6 apply-word match - 0.4 incidental-fields penalty
= 0.2) to clear detect_state's 0.5 confidence floor, fell to UNKNOWN, and
the run failed with "could not classify page state" despite being an
entirely ordinary, correctly-Apply-lickable landing page.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import GenericAdapter

_DUKE_SHAPED_LANDING_PAGE = """
<html><body>
  <input type="text" name="q" placeholder="Search by Keyword">
  <input type="submit" value="Search Jobs">
  <input type="number" name="frequency" required>
  <h1>SAP Senior Software Engineer</h1>
  <p>The Duke University IT team is seeking a SAP Senior Software Engineer...</p>
  <a href="https://careers.duke.edu/talentcommunity/apply/12345/">Apply now &raquo;</a>
</body></html>
"""

_GREENHOUSE_SHAPED_SAME_PAGE_FORM = """
<html><body>
  <h1>Software Engineer</h1>
  <a href="#application-form">Apply</a>
  <form id="application-form">
    <input type="text" name="first_name">
    <input type="text" name="last_name">
    <input type="email" name="email">
  </form>
</body></html>
"""


async def _gather_signals_for(html: str) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html, wait_until="domcontentloaded")
        signals = await GenericAdapter()._gather_signals(page)
        await browser.close()
        return signals


class TestIncidentalFieldsPenaltyScopedToSamePageApply:
    @pytest.mark.asyncio
    async def test_cross_page_apply_link_not_penalized_by_incidental_fields(self):
        signals = await _gather_signals_for(_DUKE_SHAPED_LANDING_PAGE)
        assert signals["non_file_field_count"] >= 2
        assert signals["apply_link_is_cross_page"] is True
        score = GenericAdapter()._score_landing(signals)
        assert score >= 0.5

    @pytest.mark.asyncio
    async def test_same_page_apply_anchor_still_penalized(self):
        signals = await _gather_signals_for(_GREENHOUSE_SHAPED_SAME_PAGE_FORM)
        assert signals["non_file_field_count"] >= 2
        assert signals["apply_link_is_cross_page"] is False
        score = GenericAdapter()._score_landing(signals)
        assert score < 0.5
