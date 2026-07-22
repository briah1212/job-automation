"""Regression test: _fill_credential_form must fill non-credential fields
on the same page, and fall back to a generic "Next" control when nothing
login/register-worded exists at all.

Found live testing a real application reached via LinkedIn: Epic's real
Avature-hosted careers portal has a 17-field "Employment Inquiry" page
that combines account credentials (email/password) with other real,
required application questions, advanced by a completely generic "Next"
button - not "Sign In"/"Register"/any credential-form wording at all.
Before this fix, _fill_credential_form only ever filled email/password and
searched for login/register-worded buttons, so it left every other
required field empty and failed with "No submit control found on
credential form" even though a perfectly usable "Next" button was right
there.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import GenericAdapter
from browser_worker.models import ApplicationData
from browser_worker.services.field_mapper import FieldMapper
from browser_worker.state import RunContext

_HYBRID_CREDENTIAL_AND_APPLICATION_PAGE = """
<html><body>
  <form onsubmit="return false">
    <h1>Employment Inquiry - Software Developer</h1>
    <label for="username">Email</label><input type="email" id="username" name="username">
    <label for="password">Password</label><input type="password" id="password" name="password">
    <label for="first_name">First Name</label><input type="text" id="first_name" name="first_name">
    <label for="last_name">Last Name</label><input type="text" id="last_name" name="last_name">
    <button type="submit" id="next-btn">Next</button>
  </form>
</body></html>
"""


@pytest.fixture
async def pw_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(_HYBRID_CREDENTIAL_AND_APPLICATION_PAGE, wait_until="domcontentloaded")
        yield page
        await browser.close()


def _make_ctx() -> RunContext:
    ctx = RunContext(
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
    ctx.credential = {"email": "vault@example.com", "password": "vault-pass", "status": "active", "created": True}
    return ctx


@pytest.mark.asyncio
async def test_fills_non_credential_fields_on_a_hybrid_page(pw_page):
    ctx = _make_ctx()
    result = await GenericAdapter()._handle_login(pw_page, ctx)

    assert result.success is True
    assert await pw_page.input_value("#first_name") == "Jane"
    assert await pw_page.input_value("#last_name") == "Doe"
    assert await pw_page.input_value("#username") == "vault@example.com"


@pytest.mark.asyncio
async def test_falls_back_to_generic_next_button(pw_page):
    """The only clickable control is "Next" - no login/register/submit
    wording exists at all - must still succeed, not error out."""
    ctx = _make_ctx()
    result = await GenericAdapter()._handle_login(pw_page, ctx)

    assert result.success is True
