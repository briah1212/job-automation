"""Regression test for GenericAdapter.inspect_form's label extraction on
forms that associate a label with its field through DOM position rather
than a semantic <label for="..."> - discovered against a real Lever posting
during production validation (docs/browser-state-machine-design.md).

Lever's custom "Cards" question widget (used for repeatable groups like
education history) renders a `.application-label` div as a plain sibling of
the `.application-field` div wrapping the actual input, with no for/id link
at all. Before this fix, GenericAdapter's only fallback was prettifying the
raw `name` attribute, which for a Cards field looks like
"cards[d54adf7b-3148-4095-93bb-72bef32a61f8][field1]" - meaningless to both
a human reviewer and the field-mapping/question agent that has to decide
what value belongs there. The real page paused the run on exactly this
mangled label.

The fixture below reproduces that structure directly (not a live fetch) so
this test has no network dependency; the exact markup was captured from the
real page's DOM snapshot via the replay/debug system.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import GenericAdapter

_LEVER_CARDS_FIXTURE = """
<html><body><form>
  <ul>
    <li class="application-question custom-question">
      <div>
        <div class="application-label full-width textarea">
          <div class="text">High School Name<span class="required">&#10033;</span></div>
        </div>
        <div class="application-field full-width required-field">
          <textarea class="card-field-input"
                    name="cards[d54adf7b-3148-4095-93bb-72bef32a61f8][field0]"
                    required></textarea>
        </div>
      </div>
    </li>
    <li class="application-question custom-question">
      <div>
        <div class="application-label full-width dropdown">
          <div class="text">Year of High School Graduation<span class="required">&#10033;</span></div>
        </div>
        <div class="application-field full-width required-field">
          <div class="application-dropdown">
            <select name="cards[d54adf7b-3148-4095-93bb-72bef32a61f8][field1]" required>
              <option value="">Select...</option>
              <option value="2026">2026</option>
            </select>
          </div>
        </div>
      </div>
    </li>
  </ul>
  <label for="email_input">Email</label>
  <input type="email" id="email_input" name="email">
  <button type="submit">Submit</button>
</form></body></html>
"""


@pytest.fixture
async def pw_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        yield page
        await browser.close()


@pytest.mark.asyncio
async def test_sibling_div_label_resolves_for_textarea(pw_page):
    await pw_page.set_content(_LEVER_CARDS_FIXTURE, wait_until="domcontentloaded")
    form = await GenericAdapter().inspect_form(pw_page)

    field = next(f for f in form.fields if f.name.endswith("[field0]"))
    assert field.label == "High School Name"


@pytest.mark.asyncio
async def test_sibling_div_label_resolves_for_select(pw_page):
    await pw_page.set_content(_LEVER_CARDS_FIXTURE, wait_until="domcontentloaded")
    form = await GenericAdapter().inspect_form(pw_page)

    field = next(f for f in form.fields if f.name.endswith("[field1]"))
    assert field.label == "Year of High School Graduation"


@pytest.mark.asyncio
async def test_semantic_label_for_still_takes_priority(pw_page):
    """A real <label for="..."> match must not be overridden by the sibling-div
    fallback, even though the input's own class could plausibly match it."""
    await pw_page.set_content(_LEVER_CARDS_FIXTURE, wait_until="domcontentloaded")
    form = await GenericAdapter().inspect_form(pw_page)

    field = next(f for f in form.fields if f.name == "email")
    assert field.label == "Email"
