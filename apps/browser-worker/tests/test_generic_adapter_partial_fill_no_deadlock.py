"""Regression test: a partially-filled single-page form must classify as
APPLICATION, not tie with (or lose to) SUBMIT_READY.

Found live against a real Ashby posting during production validation
(docs/browser-state-machine-design.md): once has_any_filled_field/
resume_already_attached let APPLICATION and SUBMIT_READY both score 0.5,
they tied every single loop iteration (APPLICATION wins ties, the safe
side) - but since nothing about the page's DOM state changed between one
_handle_application_page call and the next (every resolvable field kept
resolving to the same value), the run just re-filled the same fields
forever until it exhausted MAX_TRANSITIONS, never reaching SUBMIT_READY
even though the fields genuinely were all filled correctly. The fix adds
has_unfilled_visible_field so APPLICATION wins outright (no tie) while
real work remains, and only SUBMIT_READY once nothing empty is left.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import GenericAdapter
from browser_worker.state import BrowserState

_PARTIALLY_FILLED_FORM = """
<html><body>
  <h1>Some Job</h1>
  <div>
    <label for="name">Name</label><input type="text" id="name" name="name" value="Jane Doe">
    <label for="email">Email</label><input type="email" id="email" name="email" value="">
    <button type="submit">Submit Application</button>
  </div>
</body></html>
"""

_FULLY_FILLED_FORM = """
<html><body>
  <h1>Some Job</h1>
  <div>
    <label for="name">Name</label><input type="text" id="name" name="name" value="Jane Doe">
    <label for="email">Email</label><input type="email" id="email" name="email" value="jane@example.com">
    <button type="submit">Submit Application</button>
  </div>
</body></html>
"""


@pytest.fixture
async def pw_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        yield page
        await browser.close()


@pytest.mark.asyncio
async def test_partially_filled_form_does_not_classify_as_submit_ready(pw_page):
    await pw_page.set_content(_PARTIALLY_FILLED_FORM, wait_until="domcontentloaded")
    state, _ = await GenericAdapter().detect_state(pw_page)
    assert state != BrowserState.SUBMIT_READY


@pytest.mark.asyncio
async def test_fully_filled_form_can_reach_submit_ready(pw_page):
    await pw_page.set_content(_FULLY_FILLED_FORM, wait_until="domcontentloaded")
    state, _ = await GenericAdapter().detect_state(pw_page)
    assert state == BrowserState.SUBMIT_READY
