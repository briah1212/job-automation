"""Regression test: GenericAdapter._handle_landing must verify its Apply
click actually changed the page before reporting success.

Found during real-ATS validation against a real Workday posting: a visible,
valid Apply link existed and Playwright's click() raised no error, but the
page never navigated or changed content (likely bot detection or an
auth-gated flow on Workday's side - unconfirmed, but reproducible). Before
this fix, the handler unconditionally returned success, so the state
machine kept re-detecting the same unchanged LANDING page every loop
iteration until it burned the entire MAX_TRANSITIONS/wall-clock budget (40
identical checkpoints) before finally escalating with a vague "state
machine exceeded transition/time budget" error - now it fails immediately
with a specific, actionable one.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import GenericAdapter
from browser_worker.services.field_mapper import FieldMapper
from browser_worker.state import RunContext

_DEAD_APPLY_BUTTON_PAGE = """
<html><body>
  <h1>Some Job</h1>
  <button id="apply" onclick="void(0)">Apply</button>
</body></html>
"""

_WORKING_APPLY_LINK_PAGE = """
<html><body>
  <h1>Some Job</h1>
  <a id="apply" href="#next">Apply</a>
  <div id="landing">Landing content</div>
  <script>
    document.getElementById('apply').addEventListener('click', () => {
      document.getElementById('landing').outerHTML = '<div id="applied">Application form</div>';
    });
  </script>
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
        application_data=None,
        user_id="u1",
        field_mapper=FieldMapper(),
    )


@pytest.mark.asyncio
async def test_landing_handler_fails_when_apply_click_does_nothing(pw_page):
    await pw_page.set_content(_DEAD_APPLY_BUTTON_PAGE, wait_until="domcontentloaded")
    result = await GenericAdapter()._handle_landing(pw_page, _make_ctx())
    assert result.success is False
    assert "did not change" in result.error


@pytest.mark.asyncio
async def test_landing_handler_succeeds_when_apply_click_changes_page(pw_page):
    await pw_page.set_content(_WORKING_APPLY_LINK_PAGE, wait_until="domcontentloaded")
    result = await GenericAdapter()._handle_landing(pw_page, _make_ctx())
    assert result.success is True
