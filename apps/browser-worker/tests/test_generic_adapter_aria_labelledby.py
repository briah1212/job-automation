"""Regression test: field label resolution must check aria-labelledby,
not just <label for=id> and DOM-sibling position.

Found live testing a real Rippling posting (Just Appraised): every
field's own name/id is a fully random, opaque string (e.g. "8PpiPJq9jw")
with zero semantic relationship to what the field asks - no
<label for=id>, and the real label text sits several DOM levels away
from the input, connected only via aria-labelledby pointing at a
<span id="field-12-label">First name</span> elsewhere in the tree.
Without resolving it, every field's label fell through to inspect_form's
last-resort raw-identifier prettification, showing an opaque
machine-generated string as the question text a human would need to
answer - confirmed live: a real pending_question surfaced with
label="Lj51Rek51Zx" instead of the field's real question text.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import GenericAdapter

_RIPPLING_SHAPED_FIELD = """
<html><body>
  <div>
    <span id="field-12-label">First name</span>
    <span>*</span>
  </div>
  <div>
    <input id="field-12" name="8PpiPJq9jw" aria-labelledby="field-12-label" aria-required="true">
  </div>
</body></html>
"""


@pytest.mark.asyncio
async def test_aria_labelledby_resolves_real_label_text():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(_RIPPLING_SHAPED_FIELD, wait_until="domcontentloaded")
        input_elem = await page.query_selector("#field-12")
        label = await GenericAdapter()._resolve_label(page, input_elem, "field-12")
        await browser.close()
        assert label == "First name"


@pytest.mark.asyncio
async def test_aria_labelledby_with_multiple_ids_concatenates():
    """The ARIA spec allows aria-labelledby to reference multiple
    space-separated IDs, concatenated in order - confirmed live: Rippling
    splits the label text and its required-marker into two separate
    spans, though that specific case is also covered by
    _TRAILING_REQUIRED_MARKER_RE's own cleanup."""
    html = """
    <html><body>
      <span id="a">Email</span>
      <span id="b">Address</span>
      <input id="field-1" aria-labelledby="a b">
    </body></html>
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html, wait_until="domcontentloaded")
        input_elem = await page.query_selector("#field-1")
        label = await GenericAdapter()._resolve_label(page, input_elem, "field-1")
        await browser.close()
        assert label == "Email Address"
