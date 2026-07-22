"""Regression test: GenericAdapter must support radio-button-group
questions - discovering them as a single choice-of-N field (mirroring how
<select> already works) and actually filling one, not silently skipping
the whole question forever.

Found live against a real Ashby posting during production validation
(docs/browser-state-machine-design.md): a "We work 5 days on-site in NYC.
If you're not local, are you willing to relocate?" question rendered as
two real <input type=radio> options sharing one `name`. Before this fix,
inspect_form added each radio as its own separate same-named field, and
fill_field's generic page.fill() fallback (the only path type=radio ever
reached) can't fill a radio input at all - the question was never filled,
which meant has_unfilled_visible_field stayed true forever and the run
exhausted MAX_TRANSITIONS stuck re-filling the same already-resolved
fields on repeat.

The fixture markup mirrors the real captured structure: a <fieldset> with
a <label> for the question (not tied via for/id to any individual radio),
and each radio option's own choice text in a separate <label for=radio_id>.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import GenericAdapter

_RADIO_GROUP_FIXTURE = """
<html><body>
  <fieldset>
    <label for="relocate-question">Are you willing to relocate?</label>
    <div>
      <input type="radio" id="relocate-yes" name="relocate_group" required>
      <label for="relocate-yes">Yes, I will relocate</label>
    </div>
    <div>
      <input type="radio" id="relocate-no" name="relocate_group" required>
      <label for="relocate-no">No, I will not relocate</label>
    </div>
  </fieldset>
</body></html>
"""


@pytest.fixture
async def pw_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(_RADIO_GROUP_FIXTURE, wait_until="domcontentloaded")
        yield page
        await browser.close()


@pytest.mark.asyncio
async def test_radio_group_discovered_as_single_field_with_options(pw_page):
    form = await GenericAdapter().inspect_form(pw_page)

    radio_fields = [f for f in form.fields if f.input_type == "radio"]
    assert len(radio_fields) == 1

    field = radio_fields[0]
    assert field.name == "relocate_group"
    assert field.required is True
    assert set(field.options) == {"Yes, I will relocate", "No, I will not relocate"}


@pytest.mark.asyncio
async def test_fill_field_checks_the_matching_radio_option(pw_page):
    form = await GenericAdapter().inspect_form(pw_page)
    field = next(f for f in form.fields if f.input_type == "radio")

    result = await GenericAdapter().fill_field(pw_page, field, "Yes, I will relocate")

    assert result.success is True
    assert await pw_page.is_checked("#relocate-yes")
    assert not await pw_page.is_checked("#relocate-no")


@pytest.mark.asyncio
async def test_fill_field_fails_on_unmatched_radio_value(pw_page):
    form = await GenericAdapter().inspect_form(pw_page)
    field = next(f for f in form.fields if f.input_type == "radio")

    result = await GenericAdapter().fill_field(pw_page, field, "Maybe, ask me later")

    assert result.success is False
