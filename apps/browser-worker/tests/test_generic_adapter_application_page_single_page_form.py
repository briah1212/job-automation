"""Regression test: _handle_application_page must not treat the absence of
a next/continue control as a failure on a single-page form.

Found live against a real Ashby posting during production validation
(docs/browser-state-machine-design.md), the same shape of bug already fixed
for _handle_resume_upload: after filling every field on a single-page form
(no multi-step flow, only a final "Submit Application" control),
navigate_next correctly reported "No next/continue control found" - but the
handler treated that as a hard failure and escalated to manual_intervention
instead of letting detect_state re-classify the now-filled page (which,
with the has_any_filled_field fix, correctly becomes SUBMIT_READY).
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import GenericAdapter
from browser_worker.models import ApplicationData
from browser_worker.services.field_mapper import FieldMapper
from browser_worker.state import RunContext

_SINGLE_PAGE_APPLICATION_FORM = """
<html><body>
  <h1>Some Job</h1>
  <div>
    <label for="first_name">First Name</label><input type="text" id="first_name" name="first_name">
    <label for="email">Email</label><input type="email" id="email" name="email">
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


def _make_ctx() -> RunContext:
    return RunContext(
        session_id="test",
        application_url="http://example.com",
        application_data=ApplicationData(
            application_id="a1", first_name="Jane", last_name="Doe",
            email="jane@example.com", phone="555-0100", linkedin="",
            work_authorization="yes", resume_path="/tmp/fake_resume.pdf", interest=None,
        ),
        user_id="u1",
        field_mapper=FieldMapper(),
    )


@pytest.mark.asyncio
async def test_succeeds_with_no_next_button_on_single_page_form(pw_page):
    await pw_page.set_content(_SINGLE_PAGE_APPLICATION_FORM, wait_until="domcontentloaded")
    result = await GenericAdapter()._handle_application_page(pw_page, _make_ctx())

    assert result.success is True
    assert await pw_page.input_value("#first_name") == "Jane"
    assert await pw_page.input_value("#email") == "jane@example.com"
