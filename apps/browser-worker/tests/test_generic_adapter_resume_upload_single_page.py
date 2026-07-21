"""Regression tests for two related bugs found running against a real Ashby
posting during production validation
(docs/browser-state-machine-design.md):

1. _score_resume_parse_wait false-positived on Ashby's static "autofill
   from resume" widget copy ("Parsing your resume. Autofilling key
   fields..."), which is placeholder text describing the widget, present
   before any file has ever been selected - not a live status. This locked
   detect_state onto RESUME_PARSE_WAIT for an entire run on a
   fully-rendered, untouched 11-field application form.

2. Once resume_parse_wait no longer masks it, _handle_resume_upload's
   real danger surfaces: on a single-page form (resume upload is just one
   field among many, not its own step), the only button matching
   _SUBMIT_BUTTON_WORDS + _NEXT_BUTTON_WORDS is the form's actual final
   "Submit Application" control. Clicking it immediately after uploading
   the resume would submit an application missing every other field,
   completely bypassing the submit_ready/awaiting_approval gate that's
   supposed to be the only path to a real submission.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import GenericAdapter
from browser_worker.services.field_mapper import FieldMapper
from browser_worker.state import BrowserState, RunContext

# Mirrors the real, live-captured Ashby structure: an "autofill from resume"
# widget with static instructional/placeholder copy, sitting on the same
# page as a full set of other application fields - not a standalone step.
_SINGLE_PAGE_FORM_WITH_AUTOFILL_WIDGET = """
<html><body>
  <h1>New Grad Software Engineer</h1>
  <form>
    <div>Upload your resume here to autofill key application fields.</div>
    <input type="file" name="resume">
    <div>Parsing your resume. Autofilling key fields...</div>
    <label for="name">Name</label><input type="text" id="name" name="name">
    <label for="email">Email</label><input type="email" id="email" name="email">
    <label for="phone">Phone</label><input type="text" id="phone" name="phone">
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


def _make_ctx(resume_path: str = "/tmp/fake_resume.pdf") -> RunContext:
    from browser_worker.models import ApplicationData

    return RunContext(
        session_id="test",
        application_url="http://example.com",
        application_data=ApplicationData(
            application_id="a1", first_name="Jane", last_name="Doe",
            email="jane@example.com", phone="555-0100", linkedin="",
            work_authorization="yes", resume_path=resume_path, interest=None,
        ),
        user_id="u1",
        field_mapper=FieldMapper(),
    )


@pytest.mark.asyncio
async def test_static_autofill_copy_does_not_score_as_resume_parse_wait(pw_page):
    """A visible, untouched file input must never let placeholder copy about
    parsing win the classification - real parsing can't be in progress yet."""
    await pw_page.set_content(_SINGLE_PAGE_FORM_WITH_AUTOFILL_WIDGET, wait_until="domcontentloaded")
    state, _ = await GenericAdapter().detect_state(pw_page)
    assert state != BrowserState.RESUME_PARSE_WAIT


@pytest.mark.asyncio
async def test_resume_upload_handler_does_not_click_final_submit_button(pw_page, tmp_path):
    """On a single-page form with no dedicated next/continue control, the
    handler must upload the file and stop - never click a submit-worded
    button, which would fire the form's real, final submission."""
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"%PDF-1.4\n%%EOF")

    await pw_page.set_content(_SINGLE_PAGE_FORM_WITH_AUTOFILL_WIDGET, wait_until="domcontentloaded")
    ctx = _make_ctx(resume_path=str(resume))

    result = await GenericAdapter()._handle_resume_upload(pw_page, ctx)

    assert result.success is True
    # The form must still be present (not submitted / navigated away).
    assert await pw_page.query_selector("form") is not None
    assert await pw_page.query_selector('input[name="name"]') is not None
