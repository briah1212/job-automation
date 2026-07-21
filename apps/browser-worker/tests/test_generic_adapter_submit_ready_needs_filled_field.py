"""Regression test: _score_submit_ready must require at least one field to
actually be filled in, not just present on the page.

A single-page application form's real "Submit Application" button is
visible from the moment the page renders - before anything has been typed.
The earlier visible_field_count > 0 gate (see
test_generic_adapter_button_text_matching.py's sibling fix) stops the
all-zero-fields false positive found against a real, unrendered Ashby
page, but doesn't stop a fully-rendered, completely untouched form from
also scoring submit_ready just because fields exist. This is the same
"keep submission authorization outside the LLM" boundary - the single most
dangerous misclassification this adapter can make.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import GenericAdapter
from browser_worker.state import BrowserState

_EMPTY_APPLICATION_PAGE = """
<html><body>
  <h1>Some Job</h1>
  <form>
    <label for="name">Name</label><input type="text" id="name" name="name">
    <label for="email">Email</label><input type="email" id="email" name="email">
    <button type="submit">Submit Application</button>
  </form>
</body></html>
"""

_FILLED_APPLICATION_PAGE = """
<html><body>
  <h1>Some Job</h1>
  <form>
    <label for="name">Name</label><input type="text" id="name" name="name" value="Jane Doe">
    <label for="email">Email</label><input type="email" id="email" name="email" value="jane@example.com">
    <button type="submit">Submit Application</button>
  </form>
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
async def test_unfilled_form_never_scores_submit_ready(pw_page):
    await pw_page.set_content(_EMPTY_APPLICATION_PAGE, wait_until="domcontentloaded")
    state, _ = await GenericAdapter().detect_state(pw_page)
    assert state != BrowserState.SUBMIT_READY


@pytest.mark.asyncio
async def test_filled_form_can_score_submit_ready(pw_page):
    await pw_page.set_content(_FILLED_APPLICATION_PAGE, wait_until="domcontentloaded")
    state, _ = await GenericAdapter().detect_state(pw_page)
    assert state == BrowserState.SUBMIT_READY
