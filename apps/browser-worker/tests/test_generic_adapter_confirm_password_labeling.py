"""Regression test: _handle_login must recognize a confirm-password field
by more than the literal word "confirm" in its `name`/`id`.

Found live testing a real Taleo posting (Costco): the second password
field's name/id is "cwsPassword_2" (no relation to "confirm") and its
visible label is "Re-type new password:". Before this fix, confirm_field
detection only checked `"confirm" in f.name.lower()`, so it never matched -
primary_password_field then greedily became whichever password field
happened to come first in DOM order, and the OTHER password field was left
permanently empty (nothing in _handle_login fills any password field beyond
primary_password_field/confirm_field). Client-side validation then silently
blocked the "next" click from ever advancing - no error, no exception, the
run just re-filled the same page forever until the stall detector gave up.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import GenericAdapter
from browser_worker.models import ApplicationData
from browser_worker.services.field_mapper import FieldMapper
from browser_worker.state import RunContext

_TALEO_SHAPED_REGISTER_PAGE = """
<html><body>
  <form onsubmit="return false">
    <h1>1. Register</h1>
    <label for="cwsEmail">Email</label><input type="email" id="cwsEmail" name="cwsEmail">
    <label for="cwsPassword">Password</label><input type="password" id="cwsPassword" name="cwsPassword">
    <label for="cwsPassword_2">Re-type new password:</label><input type="password" id="cwsPassword_2" name="cwsPassword_2">
  </form>
  <a href="#" id="next-link">next</a>
</body></html>
"""


@pytest.fixture
async def pw_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(_TALEO_SHAPED_REGISTER_PAGE, wait_until="domcontentloaded")
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
async def test_retype_labeled_field_is_filled_as_confirm_password(pw_page):
    ctx = _make_ctx()
    result = await GenericAdapter()._handle_login(pw_page, ctx)

    assert result.success is True
    assert await pw_page.input_value("#cwsPassword") == "vault-pass"
    assert await pw_page.input_value("#cwsPassword_2") == "vault-pass"
