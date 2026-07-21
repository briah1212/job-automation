"""Regression test for GenericAdapter's landing/review scoring requiring an
exact button-text match instead of a substring match - discovered against a
real Ashby posting during production validation
(docs/browser-state-machine-design.md).

The real button read "Apply for this job", not the bare word "apply" or
"apply now" that _score_landing checked for via `b in ("apply", "apply
now")` (list membership, not substring search) - every other button check
in this adapter, including the one that actually clicks it
(_find_button_by_words), already matches by substring. The mismatch meant
detect_state scored the real landing page too low (0.3) to ever try
clicking Apply, so the run never got past the job description tab to reach
the actual application form. _score_review had the identical bug on its
submit-button check.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import GenericAdapter
from browser_worker.state import BrowserState

_ASHBY_LIKE_LANDING = """
<html><body>
  <h1>New Grad Software Engineer</h1>
  <button>Overview</button>
  <button>Application</button>
  <button>Apply for this job</button>
</body></html>
"""

_REVIEW_WITH_WORDY_SUBMIT_BUTTON = """
<html><body>
  <h1>Review your application</h1>
  <input type="checkbox" required>
  <button>Submit Your Application Now</button>
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
async def test_landing_detected_with_wordy_apply_button(pw_page):
    await pw_page.set_content(_ASHBY_LIKE_LANDING, wait_until="domcontentloaded")
    state, confidence = await GenericAdapter().detect_state(pw_page)
    assert state == BrowserState.LANDING
    assert confidence >= 0.5


@pytest.mark.asyncio
async def test_review_detected_with_wordy_submit_button(pw_page):
    await pw_page.set_content(_REVIEW_WITH_WORDY_SUBMIT_BUTTON, wait_until="domcontentloaded")
    state, confidence = await GenericAdapter().detect_state(pw_page)
    assert state == BrowserState.REVIEW
    assert confidence >= 0.5
