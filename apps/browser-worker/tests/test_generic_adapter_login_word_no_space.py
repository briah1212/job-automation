"""Regression test: login/signup-detection word lists must match a bare
"Login" button, not only "Log In" (with a space).

Found live testing a real Taleo posting (Costco): its actual login button
text is the single word "Login". Every "log in"/"sign in" word list in
generic_adapter.py previously checked only the spaced form, so
`"log in" in "login"` (substring match) was False and every one of them
silently missed a real, clearly-visible login button - the run failed
with "No submit control found on credential form" despite a perfectly
usable Login button being right there on screen.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import GenericAdapter
from browser_worker.models import ApplicationData
from browser_worker.services.field_mapper import FieldMapper
from browser_worker.state import RunContext

_RETURNING_APPLICANT_LOGIN_PAGE = """
<html><body>
  <form onsubmit="return false">
    <h1>Previous Applicants</h1>
    <label for="email">Email</label><input type="email" id="email" name="email" value="hsubrian1212@gmail.com">
    <label for="password">Password</label><input type="password" id="password" name="password">
    <button type="submit" id="login-btn">Login</button>
  </form>
</body></html>
"""


@pytest.fixture
async def pw_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(_RETURNING_APPLICANT_LOGIN_PAGE, wait_until="domcontentloaded")
        yield page
        await browser.close()


def _make_ctx(created: bool) -> RunContext:
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
    ctx.credential = {"email": "vault@example.com", "password": "vault-pass", "status": "active", "created": created}
    return ctx


@pytest.mark.asyncio
async def test_bare_login_button_is_found_and_clicked(pw_page):
    """credential["created"]=True (a fresh vault credential expecting to
    register) makes opposite_intent_words - the ("log in", "login", ...)
    tier - the one actually exercised here, matching the real Taleo
    scenario where the vault created a new credential but the ATS's own
    system already knew the email from a prior real application."""
    ctx = _make_ctx(created=True)
    result = await GenericAdapter()._handle_login(pw_page, ctx)

    assert result.success is True
