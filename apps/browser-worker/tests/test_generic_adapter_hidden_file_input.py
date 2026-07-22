"""Regression test: a file input hidden by its OWN styling (a separate
visible "Upload" trigger elsewhere on the page) must be discovered, but a
file input hidden because a whole ANCESTOR container is inactive must not.

Found live testing a real application reached via LinkedIn: Epic's real
Avature-hosted careers portal hides its actual <input type=file> entirely
(display:none) behind a separate visible "Upload a resume" label/icon -
Playwright's :visible pseudo-class excludes it completely (this is a
stricter hiding than Ashby's already-handled 1x1-but-still-:visible
pattern), so inspect_form never found it and has_file_input was always
False, meaning the whole resume_upload/application scoring pipeline never
even considered this page as having a file to upload.

The naive fix (include every file input regardless of visibility) breaks
the mock-ats fixture, which instead renders every stage's markup in the
DOM simultaneously and hides whole INACTIVE stage <section>s - that
fixture's OWN file input would get wrongly resurrected on every other
stage. The fixture below reproduces both real shapes side by side.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import GenericAdapter

_AVATURE_LIKE_HIDDEN_FILE_INPUT = """
<html><body>
  <form>
    <h1>How would you like to apply?</h1>
    <div>
      <label for="resume-upload">Upload a resume</label>
      <input type="file" id="resume-upload" style="display:none">
    </div>
  </form>
</body></html>
"""

_MOCK_ATS_LIKE_INACTIVE_STAGE = """
<html><body>
  <section data-stage="application" style="display:block;">
    <form>
      <h1>Application</h1>
      <label for="name">Name</label><input type="text" id="name" name="name">
    </form>
  </section>
  <section data-stage="resume-upload" style="display:none;">
    <form>
      <label for="resume">Resume</label>
      <input type="file" id="resume" name="resume">
    </form>
  </section>
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
async def test_finds_file_input_hidden_by_its_own_styling(pw_page):
    await pw_page.set_content(_AVATURE_LIKE_HIDDEN_FILE_INPUT, wait_until="domcontentloaded")
    form = await GenericAdapter().inspect_form(pw_page)

    file_fields = [f for f in form.fields if f.input_type == "file"]
    assert len(file_fields) == 1
    assert file_fields[0].name == "resume-upload"


@pytest.mark.asyncio
async def test_ignores_file_input_belonging_to_an_inactive_ancestor_section(pw_page):
    await pw_page.set_content(_MOCK_ATS_LIKE_INACTIVE_STAGE, wait_until="domcontentloaded")
    form = await GenericAdapter().inspect_form(pw_page)

    file_fields = [f for f in form.fields if f.input_type == "file"]
    assert file_fields == []
    # The active stage's real, unrelated text field must still be found -
    # this isn't just "find nothing", the rest of the page still works.
    assert any(f.name == "name" for f in form.fields)


@pytest.mark.asyncio
async def test_has_file_input_signal_matches_the_same_rule(pw_page):
    adapter = GenericAdapter()

    await pw_page.set_content(_AVATURE_LIKE_HIDDEN_FILE_INPUT, wait_until="domcontentloaded")
    signals = await adapter._gather_signals(pw_page)
    assert signals["has_file_input"] is True

    await pw_page.set_content(_MOCK_ATS_LIKE_INACTIVE_STAGE, wait_until="domcontentloaded")
    signals = await adapter._gather_signals(pw_page)
    assert signals["has_file_input"] is False
