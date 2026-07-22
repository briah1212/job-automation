"""Regression test: <select> options must be matched/filled by their
human-readable text, not their raw `value` attribute.

Found live testing a real application reached via LinkedIn: Epic's real
Avature-hosted careers portal uses opaque numeric option values
(value="28074">Bachelor's Degree (completed or in progress)) with the
actual meaning only in the option's text content. Before this fix,
inspect_form populated field.options with these raw values ("28074",
"28078", ...), so _constrain_to_options could never match any agent-
generated or previously-approved answer against any dropdown on this
kind of site - a correct, exact, pre-approved answer for "Degree Level"
("Bachelor's Degree (completed or in progress)") could never map to
"28074", so the question deferred to the user every single time, even on
a fresh run using an answer already on file from an earlier run.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import GenericAdapter
from browser_worker.services.field_resolution import _constrain_to_options

_OPAQUE_VALUE_SELECT_PAGE = """
<html><body>
  <form>
    <label for="degree">Degree Level</label>
    <select id="degree" name="degree">
      <option value="">Select an option</option>
      <option value="28074">Bachelor's Degree (completed or in progress)</option>
      <option value="28078">Master's Degree</option>
      <option value="28079">PhD</option>
    </select>
  </form>
</body></html>
"""


@pytest.fixture
async def pw_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(_OPAQUE_VALUE_SELECT_PAGE, wait_until="domcontentloaded")
        yield page
        await browser.close()


@pytest.mark.asyncio
async def test_options_are_the_readable_text_not_the_raw_value(pw_page):
    form = await GenericAdapter().inspect_form(pw_page)
    field = next(f for f in form.fields if f.name == "degree")

    assert "Bachelor's Degree (completed or in progress)" in field.options
    assert "28074" not in field.options


@pytest.mark.asyncio
async def test_an_exact_approved_answer_now_confidently_maps(pw_page):
    """The actual bug: an exact, previously-approved answer (from
    ReusableAnswer) could never constrain to any option when options were
    raw opaque values - it can now."""
    form = await GenericAdapter().inspect_form(pw_page)
    field = next(f for f in form.fields if f.name == "degree")

    resolved = _constrain_to_options("Bachelor's Degree (completed or in progress)", field)
    assert resolved == "Bachelor's Degree (completed or in progress)"


@pytest.mark.asyncio
async def test_fill_field_selects_the_correct_option_by_label(pw_page):
    form = await GenericAdapter().inspect_form(pw_page)
    field = next(f for f in form.fields if f.name == "degree")

    result = await GenericAdapter().fill_field(pw_page, field, "Bachelor's Degree (completed or in progress)")

    assert result.success is True
    assert await pw_page.eval_on_selector("#degree", "el => el.value") == "28074"
