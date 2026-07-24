"""Regression test: fill_field must not report success when a native
input's own format constraint silently rejected the value.

CRITICAL finding, confirmed live against a real Recruitee posting (TYTAN
Technologies): a "What is your salary expectation?" question rendered as
<input type="number">, and an entirely reasonable free-text answer
("Negotiable, based on role scope and total compensation") silently
produced an empty required field - page.fill() doesn't raise when a
native input's type constraint rejects text that doesn't match its
expected format, it just leaves the field empty with no error anywhere.
fill_field reported success, ctx.filled_fields recorded the field as
done, and the run moved on genuinely believing a required field was
filled when it was blank - only the target site's own client-side
validation (not something to rely on) stood between this and a
submission with a missing required field. The same failure mode hit a
type="date" field asked in free text ("Immediately") on the same form.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import GenericAdapter
from browser_worker.models import FormField

_NUMBER_FIELD_PAGE = """
<html><body>
  <label for="salary">Salary expectation</label>
  <input type="number" id="salary" name="salary">
</body></html>
"""

_TEXT_FIELD_PAGE = """
<html><body>
  <label for="notes">Notes</label>
  <input type="text" id="notes" name="notes">
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
async def test_non_numeric_answer_into_number_field_reports_failure(pw_page):
    await pw_page.set_content(_NUMBER_FIELD_PAGE)
    field = FormField(
        name="salary", label="Salary expectation", input_type="number",
        required=True, options=None, placeholder=None, selector="#salary",
    )
    result = await GenericAdapter().fill_field(
        pw_page, field, "Negotiable, based on role scope and total compensation"
    )
    assert result.success is False
    assert await pw_page.input_value("#salary") == ""


@pytest.mark.asyncio
async def test_valid_numeric_answer_into_number_field_still_succeeds(pw_page):
    await pw_page.set_content(_NUMBER_FIELD_PAGE)
    field = FormField(
        name="salary", label="Salary expectation", input_type="number",
        required=True, options=None, placeholder=None, selector="#salary",
    )
    result = await GenericAdapter().fill_field(pw_page, field, "95000")
    assert result.success is True
    assert await pw_page.input_value("#salary") == "95000"


@pytest.mark.asyncio
async def test_ordinary_text_field_unaffected(pw_page):
    await pw_page.set_content(_TEXT_FIELD_PAGE)
    field = FormField(
        name="notes", label="Notes", input_type="text",
        required=False, options=None, placeholder=None, selector="#notes",
    )
    result = await GenericAdapter().fill_field(pw_page, field, "Looking forward to it")
    assert result.success is True
    assert await pw_page.input_value("#notes") == "Looking forward to it"
