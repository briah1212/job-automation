"""Regression test: _handle_login/_handle_create_account must fetch a
credential themselves when ctx.credential isn't already set, instead of
assuming _handle_apply always ran first.

Found live testing a real application reached via LinkedIn: Epic's real
Avature-hosted careers portal goes straight from resume-upload to a
register/login FORM, with no distinct "apply" landing step in between to
have populated ctx.credential via _handle_apply at all. Before this fix,
_fill_credential_form (shared by both handlers) unconditionally required
ctx.credential to already be set and failed with "No credential available"
on every such site, forever - there was no path to ever populate it.
"""
from unittest.mock import AsyncMock, patch

import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import GenericAdapter
from browser_worker.models import ApplicationData
from browser_worker.services.field_mapper import FieldMapper
from browser_worker.state import RunContext

_LOGIN_FORM_PAGE = """
<html><body>
  <form onsubmit="return false">
    <label for="email">Email</label><input type="email" id="email" name="email">
    <label for="password">Password</label><input type="password" id="password" name="password">
    <button type="submit">Log in</button>
  </form>
</body></html>
"""

_FAKE_CREDENTIAL = {
    "email": "vault-account@example.com",
    "password": "vault-generated-password",
    "status": "active",
    "created": False,
}


@pytest.fixture
async def pw_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(_LOGIN_FORM_PAGE, wait_until="domcontentloaded")
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
async def test_login_handler_fetches_credential_when_not_already_set(pw_page):
    ctx = _make_ctx()
    assert ctx.credential is None

    with patch(
        "browser_worker.adapters.generic_adapter.get_or_create_credential",
        new=AsyncMock(return_value=_FAKE_CREDENTIAL),
    ):
        result = await GenericAdapter()._handle_login(pw_page, ctx)

    assert result.success is True
    assert ctx.credential == _FAKE_CREDENTIAL
    assert await pw_page.input_value("#email") == "vault-account@example.com"


@pytest.mark.asyncio
async def test_login_handler_reuses_already_set_credential_without_refetching(pw_page):
    ctx = _make_ctx()
    ctx.credential = _FAKE_CREDENTIAL

    fetch_mock = AsyncMock(return_value=_FAKE_CREDENTIAL)
    with patch("browser_worker.adapters.generic_adapter.get_or_create_credential", new=fetch_mock):
        result = await GenericAdapter()._handle_login(pw_page, ctx)

    assert result.success is True
    fetch_mock.assert_not_called()


@pytest.mark.asyncio
async def test_login_handler_fails_gracefully_when_vault_lookup_fails(pw_page):
    ctx = _make_ctx()

    with patch(
        "browser_worker.adapters.generic_adapter.get_or_create_credential",
        new=AsyncMock(side_effect=RuntimeError("vault unreachable")),
    ):
        result = await GenericAdapter()._handle_login(pw_page, ctx)

    assert result.success is False
    assert "vault unreachable" in result.error
