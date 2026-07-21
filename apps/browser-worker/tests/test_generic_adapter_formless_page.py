"""Regression test: GenericAdapter.inspect_form must fall back to scanning
the whole page when there's no semantic <form> element.

Found live against a real Ashby posting during production validation
(docs/browser-state-machine-design.md): the real application page had zero
<form> elements anywhere, but 11 real, fillable visible inputs sitting in
plain <div>s - a React component tree submitted via fetch/JS, not native
form submission. Before this fix, every field-filling handler
(_handle_profile_setup, _handle_resume_upload, _handle_application_page,
_handle_review - all of which call inspect_form) would unconditionally
raise ValueError("No visible form found on page") on any such page.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import GenericAdapter

_FORMLESS_APPLICATION_PAGE = """
<html><body>
  <div class="application">
    <label for="name">Name</label><input type="text" id="name" name="name">
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


@pytest.mark.asyncio
async def test_inspect_form_finds_fields_with_no_form_element(pw_page):
    await pw_page.set_content(_FORMLESS_APPLICATION_PAGE, wait_until="domcontentloaded")
    form = await GenericAdapter().inspect_form(pw_page)

    field_names = {f.name for f in form.fields}
    assert field_names == {"name", "email"}
