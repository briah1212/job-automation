"""Regression test: button/control discovery for in-flow advancement must
recognize "I Accept"/"Accept"/"Agree" wording, not just
"Next"/"Continue"/"Proceed".

Found live testing a real Jobvite posting (NinjaOne): a "Data Consent"
interstitial requires selecting a location/language, which reveals an
"I Accept"/"I Decline" panel - "I Accept" is the real progression action,
worded differently from any _NEXT_BUTTON_WORDS entry.
_handle_application_page's advance-to-next-step search (and navigate_next,
which it calls) previously only ever searched for _NEXT_BUTTON_WORDS, so
after the one real field was filled, nothing matched "I Accept" and the
handler returned success having clicked nothing - the page never advanced,
and the run stalled on the exact same page forever until the no-progress
detector caught it.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import _ADVANCE_BUTTON_WORDS, GenericAdapter

_CONSENT_SELECT_PAGE = """
<html><body>
  <form onsubmit="return false">
    <h3>Data Consent</h3>
    <label for="jv-country-select">Location of Residence and Language:</label>
    <select id="jv-country-select" name="jv-country-select">
      <option value="">Select your location of residence and language</option>
      <option value="global">Global NINJAONE APPLICANT AND CANDIDATE PRIVACY POLICY</option>
    </select>
  </form>
  <button id="accept-btn">I Accept</button>
  <a href="#" id="decline-link">I Decline</a>
</body></html>
"""


@pytest.fixture
async def pw_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(_CONSENT_SELECT_PAGE, wait_until="domcontentloaded")
        yield page
        await browser.close()


@pytest.mark.asyncio
async def test_i_accept_button_is_found_by_advance_word_list(pw_page):
    """The actual fix: _ADVANCE_BUTTON_WORDS (used by both
    _handle_application_page's existence check and navigate_next's own
    search) includes "accept"/"agree"/"i accept"/"i agree" alongside
    "next"/"continue"/"proceed" - confirming the real "I Accept" control
    is found is the specific, targeted regression this covers."""
    btn = await GenericAdapter()._find_button_by_words(pw_page, _ADVANCE_BUTTON_WORDS)
    assert btn is not None
    text = (await btn.text_content() or "").strip().lower()
    assert "accept" in text


@pytest.mark.asyncio
async def test_i_accept_is_not_found_by_narrow_next_words_alone(pw_page):
    """Documents exactly what broke: the OLD word list would find nothing
    on this page at all."""
    btn = await GenericAdapter()._find_button_by_words(pw_page, ("next", "continue", "proceed"))
    assert btn is None
