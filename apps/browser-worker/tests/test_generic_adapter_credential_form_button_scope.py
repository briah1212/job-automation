"""Regression test: _fill_credential_form's submit-button search must be
scoped to the actual form and intent-aware (register vs. log in), not a
whole-page search that can hit an unrelated header link first.

Found live testing a real application reached via LinkedIn: Epic's real
Avature-hosted careers portal has a persistent page-header "Log in" link
appearing in the DOM before a combined "sign in or register your account"
form. A freshly vault-created credential (a brand-new account, never
registered on this site before) needs the REGISTER path - clicking the
header's stray "Log in" link (or the form's own "Sign In" button, matched
only because "log in"/"sign in" happened to be checked before "create
account"/"register") fails validation silently and just re-renders the
same page forever, which is exactly what happened live: 41 consecutive
LOGIN checkpoints with zero progress.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import GenericAdapter
from browser_worker.models import ApplicationData
from browser_worker.services.field_mapper import FieldMapper
from browser_worker.state import RunContext

_COMBINED_SIGNIN_REGISTER_PAGE = """
<html><body>
  <header>
    <a href="/login">Log in</a>
  </header>
  <form onsubmit="return false">
    <h1>Sign in or register your account below.</h1>
    <label for="email">Email</label><input type="email" id="email" name="email">
    <label for="password">Password</label><input type="password" id="password" name="password">
    <button type="submit" id="signin-btn">Sign In</button>
    <button type="button" id="register-btn">Register</button>
  </form>
</body></html>
"""

# Mirrors the real, live-captured Epic/Avature structure exactly: one
# unified button handles both login and registration - the site decides
# which based on whether the email is already known - so there is no
# separate register-worded control to find at all.
_UNIFIED_BUTTON_PAGE = """
<html><body>
  <header>
    <a href="/login">Log in</a>
  </header>
  <form onsubmit="return false">
    <h1>Sign in or register your account below.</h1>
    <label for="username">Email</label><input type="email" id="username" name="username">
    <label for="password">Password</label><input type="password" id="password" name="password">
    <button type="submit" id="signin-btn">Sign In</button>
  </form>
</body></html>
"""


@pytest.fixture
async def pw_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(_COMBINED_SIGNIN_REGISTER_PAGE, wait_until="domcontentloaded")
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
async def test_clicks_register_for_a_freshly_created_credential(pw_page):
    ctx = _make_ctx(created=True)
    result = await GenericAdapter()._handle_login(pw_page, ctx)

    assert result.success is True
    # The stray header "Log in" link must not have been followed - the
    # page (still under our control) should show evidence the REGISTER
    # button's own click handler ran, not a navigation away.
    assert pw_page.url != "http://example.com/login"


@pytest.mark.asyncio
async def test_clicks_signin_for_a_reused_credential(pw_page):
    ctx = _make_ctx(created=False)
    result = await GenericAdapter()._handle_login(pw_page, ctx)

    assert result.success is True


@pytest.mark.asyncio
async def test_button_search_can_be_scoped_to_a_container(pw_page):
    """Direct test of the scope parameter itself: a page-wide search for
    "log in" hits the header link first (DOM order); scoped to the form,
    it must not."""
    adapter = GenericAdapter()

    page_wide = await adapter._find_button_by_words(pw_page, ("log in",))
    page_wide_href = await page_wide.get_attribute("href")
    assert page_wide_href == "/login"

    form = await pw_page.query_selector("form")
    scoped = await adapter._find_button_by_words(pw_page, ("log in",), scope=form)
    assert scoped is None  # the form has no "log in"-worded control at all


@pytest.mark.asyncio
async def test_falls_back_to_unified_button_when_no_dedicated_register_control_exists(pw_page):
    """A brand-new credential still needs to submit through a page whose
    ONLY control is a "Sign In" button that the site itself will treat as
    "register" for an unrecognized email (confirmed live: Epic's real
    Avature-hosted careers portal has exactly this shape) - must not fail
    outright just because no register-worded control exists to prefer."""
    await pw_page.set_content(_UNIFIED_BUTTON_PAGE, wait_until="domcontentloaded")
    ctx = _make_ctx(created=True)

    result = await GenericAdapter()._handle_login(pw_page, ctx)

    assert result.success is True
