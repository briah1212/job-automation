"""Regression test: once a resume is already attached (a "Replace" control
is showing, not the initial "Upload File" one), detect_state must move on
to filling the rest of the form instead of re-triggering the upload
forever.

Found live against a real Ashby posting during production validation
(docs/browser-state-machine-design.md): Ashby's file input stays in the DOM
even after a successful upload (just gains a "Replace" affordance), so
has_file_input alone can't tell "empty, needs uploading" from "already
uploaded". Without resume_already_attached, _score_resume_upload kept
re-winning every single loop iteration (re-uploading the same file each
time, harmlessly but pointlessly), and _score_application's `not
has_file_input` gate never passed even once the resume genuinely was
attached - the run exhausted MAX_TRANSITIONS without ever filling the
other 10 real fields on the page.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import GenericAdapter
from browser_worker.state import BrowserState

_FORM_WITH_ATTACHED_RESUME = """
<html><body>
  <h1>New Grad Software Engineer</h1>
  <div>
    <input type="file" name="resume">
    <span>resume.pdf</span>
    <button>Replace</button>
  </div>
  <label for="name">Name</label><input type="text" id="name" name="name">
  <label for="email">Email</label><input type="email" id="email" name="email">
  <label for="phone">Phone</label><input type="text" id="phone" name="phone">
  <button type="submit">Submit Application</button>
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
async def test_does_not_reclassify_as_resume_upload_once_attached(pw_page):
    await pw_page.set_content(_FORM_WITH_ATTACHED_RESUME, wait_until="domcontentloaded")
    state, _ = await GenericAdapter().detect_state(pw_page)
    assert state != BrowserState.RESUME_UPLOAD


@pytest.mark.asyncio
async def test_does_not_falsely_classify_as_submit_ready_before_anything_is_filled(pw_page):
    """A resume attachment alone isn't evidence the rest of a form (name,
    email, custom questions) has been filled - must not jump straight to
    submit-ready just because a "Submit Application" button is visible."""
    await pw_page.set_content(_FORM_WITH_ATTACHED_RESUME, wait_until="domcontentloaded")
    state, _ = await GenericAdapter().detect_state(pw_page)
    assert state != BrowserState.SUBMIT_READY
