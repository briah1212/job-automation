"""Regression test: apply/submit button-word matching must recognize
German wording, at least for the specific words confirmed live.

Found live testing a real Recruitee posting (TYTAN Technologies, a German
company whose career site defaults to German): the landing page's only
Apply CTA reads "Bewerben" and the real application form's submit button
reads "Senden" - neither matched any entry in _APPLY_BUTTON_WORDS or
_SUBMIT_BUTTON_WORDS (both entirely English lists), so the run failed
with "No Apply button found" and then "could not classify page state" in
turn, despite the site being an ordinary, fully-functional application
flow.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import (
    _APPLY_BUTTON_WORDS,
    _SUBMIT_BUTTON_WORDS,
    GenericAdapter,
)


@pytest.fixture
async def pw_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        yield page
        await browser.close()


@pytest.mark.asyncio
async def test_bewerben_apply_button_is_found(pw_page):
    await pw_page.set_content('<body><button>Bewerben</button></body>')
    btn = await GenericAdapter()._find_button_by_words(pw_page, _APPLY_BUTTON_WORDS)
    assert btn is not None


@pytest.mark.asyncio
async def test_senden_submit_button_is_found(pw_page):
    await pw_page.set_content('<body><button>Senden</button></body>')
    btn = await GenericAdapter()._find_button_by_words(pw_page, _SUBMIT_BUTTON_WORDS)
    assert btn is not None
