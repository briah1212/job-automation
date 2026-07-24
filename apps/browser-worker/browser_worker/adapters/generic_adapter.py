import logging
import re
from typing import List, Optional, Tuple

from playwright.async_api import Page, ElementHandle
from .base import ATSAdapter
from ..models import (
    ApplicationForm,
    FormField,
    FillResult,
    UploadResult,
    NavigationResult,
    SubmissionResult,
    ConfirmationResult,
)
from ..state import BrowserState, RunContext, StateHandlerResult
from ..services.credential_vault_client import get_or_create_credential
from ..services.field_resolution import compute_form_fingerprint, resolve_field_value
from ..services.field_visibility import is_genuinely_fillable

logger = logging.getLogger(__name__)

_NEXT_BUTTON_WORDS = ("next", "continue", "proceed")
# Confirmed live against a real Jobvite posting (NinjaOne): a "Data
# Consent" interstitial requires selecting a location/language before an
# "I Accept"/"I Decline" panel even renders - clicking "I Accept" is the
# real progression action for that step, exactly equivalent in effect to a
# "Next" button, just worded differently. _handle_application_page's
# advance-to-next-step search only ever looked for _NEXT_BUTTON_WORDS, so
# after the one real field was filled, nothing matched "I Accept" and the
# handler just returned success having clicked nothing - the page never
# advanced, and the run stalled on the exact same page forever until the
# no-progress detector caught it. Deliberately kept separate from
# _SUBMIT_BUTTON_WORDS below (a consent-accept click is an intermediate
# navigation step within the flow, not a final "submit this application"
# action) and only used for this same in-flow advancement search, not for
# anything that would trigger a real SUBMITTED classification.
_ADVANCE_BUTTON_WORDS = _NEXT_BUTTON_WORDS + ("accept", "agree", "i accept", "i agree")
# "senden" confirmed live against the same real Recruitee posting (TYTAN
# Technologies) that motivated _APPLY_BUTTON_WORDS' "bewerben" addition -
# its real application form's submit button reads "Senden" (German for
# "Send"/"Submit"), not any English word. Without it, _score_application's
# "genuine submit button alongside unfilled fields" bonus never fired,
# leaving the score at exactly 0.4 (non_file_field_count alone) - just
# under detect_state's 0.5 floor. Same broader known i18n gap as
# _APPLY_BUTTON_WORDS' comment describes; only this one confirmed-live word
# added here, not a general translation pass.
_SUBMIT_BUTTON_WORDS = ("submit", "apply", "send application", "finish", "senden")
# Confirmed live against a real SmartRecruiters posting: its primary CTA is
# "I'm Interested", not any word containing "apply" - _score_landing scored
# it too low to ever cross the detect_state confidence floor, so the run
# paused as "unsupported_flow" before a single click happened.
#
# "bewerben" confirmed live against a real Recruitee posting (TYTAN
# Technologies, a German company whose career site defaults to German) -
# its only Apply CTA is "Bewerben", German for "Apply". This whole file's
# word-matching is English-only throughout (every _..._WORDS constant) -
# a real, broader known gap (full internationalization would need every
# such list translated, not just this one word for this one language),
# not attempted here beyond this single confirmed-live case.
_APPLY_BUTTON_WORDS = ("apply now", "apply", "i'm interested", "bewerben")
# Confirmed live against a real Taleo posting (Costco): the second
# password field's own `name`/`id` attributes are "cwsPassword_2" (no
# relation to "confirm") and its visible label is "Re-type new password:"
# - matching neither the word "confirm" nor even appearing as a `name`.
# Checked against both a field's `name` AND its resolved `label`, and
# against several common real-world phrasings, not just "confirm" - a
# missed confirm-field left it permanently unfilled (fill_field/
# _handle_login only ever fill primary_password_field and confirm_field
# explicitly, nothing else), which client-side validation then silently
# blocked forever: the "next" click never actually failed or errored, it
# just never advanced, indistinguishable from a submit-control-not-found
# case without inspecting a live screenshot.
_CONFIRM_PASSWORD_KEYWORDS = ("confirm", "retype", "re-type", "re type", "verify", "repeat")
# Confirmed live against a real Taleo posting (Costco): its actual login
# button text is the single word "Login" - every login/signup-detection
# word list in this file previously only checked "log in" (WITH a space),
# so `"log in" in "login"` is False and every one of them silently missed
# it, real button plainly visible in a live screenshot notwithstanding.
# "Sign In"/"Signin" carries the identical risk, included for the same
# reason even though not yet confirmed live on a specific site.
_LOGIN_WORDS = ("log in", "login", "sign in", "signin")

# Fallback label lookup for forms that associate a label with its field
# through DOM position rather than a semantic <label for="..."> - e.g.
# Lever's custom "Cards" question widget (education history, and similar
# repeatable-question groups) renders a `.application-label` div as a
# sibling of the `.application-field` div wrapping the actual input,
# with no `for`/`id` link between them at all. Without this, inspect_form's
# only fallback is prettifying the raw `name` attribute, which for a Cards
# field looks like "cards[d54adf7b-3148-4095-93bb-72bef32a61f8][field1]" -
# meaningless to both a human reviewer and the field-mapping/question agent
# that has to decide what value belongs there.
_SIBLING_LABEL_JS = """
el => {
    // Start from the parent, not el itself - an input/textarea can carry
    // its own "field"-ish class (e.g. Lever's "card-field-input"), which
    // would otherwise short-circuit closest() on the element itself instead
    // of walking up to the actual label/field container pairing.
    const start = el.parentElement || el;
    const fieldContainer = start.closest('[class*="field" i]');
    if (!fieldContainer) return null;
    let sib = fieldContainer.previousElementSibling;
    while (sib) {
        if (/label/i.test(sib.className || '')) {
            const text = (sib.textContent || '').trim();
            if (text) return text;
        }
        sib = sib.previousElementSibling;
    }
    return null;
}
"""
# KNOWN GAP, NOT fixed here: this fallback (and _resolve_label's
# aria-labelledby check above it) both require SOME kind of semantic
# marker to find a field's real label - a className containing "field"/
# "label" here, an actual aria-labelledby/<label for> there. Confirmed
# live against a real Rippling posting (Just Appraised): every plain text
# input (first/last name, email, phone number, location, LinkedIn,
# website, race - 9 fields) correctly resolves via aria-labelledby, but
# every custom role="combobox" dropdown widget (a phone country-code
# sub-selector, plus a whole block of screening questions - "What industry
# is Just Appraised in?", "What backend programming language are you most
# proficient with?", and more) has NEITHER an aria-labelledby NOR any
# className resembling "field"/"label" - their real label is genuinely
# just visually-adjacent text with zero programmatic link to the input at
# all, and every class name involved is an opaque CSS-in-JS hash (e.g.
# "css-15epsmk etc2niq2"). A general fix would need a className-agnostic
# "nearest preceding text content, structurally" heuristic - not attempted
# here, since a broader/fuzzier version of this fallback risks grabbing
# the WRONG nearby text (help copy, an unrelated heading) on some other
# real site, and every plain text input on this same real form already
# resolves correctly via aria-labelledby.
# True if no ANCESTOR (not the element itself) hides the element behind
# substantial alternate content - deliberately ignores the element's own
# display/visibility, since a file input is routinely hidden by its own
# styling behind a separate visible "Upload" trigger elsewhere on the same
# active page. A small hidden ancestor (few descendants) is tolerated and
# walked past - confirmed live against Epic's real Avature-hosted careers
# portal, whose actual <input type=file> sits inside a 3-element wrapper
# div (id="resumeFileField": a <p>, a <label>, the input) that's
# display:none purely to hide the native control in favor of a separate
# styled trigger link elsewhere on the SAME visible page. What this must
# still catch: a whole ancestor representing an entire inactive page/
# stage/step (the mock-ats fixture renders every stage's markup in the DOM
# simultaneously and hides inactive ones this way) - those are
# substantially larger (mock-ats's hidden resume-upload stage has a
# heading, a form, a label, the input, hint text, and a button: 8
# elements), so a hidden ancestor above a small size is treated as a real
# "this isn't the active page" signal instead of a widget-hiding detail.
_MAX_TOLERATED_HIDDEN_WRAPPER_DESCENDANTS = 6

# KNOWN GAP, NOT fixed here (confirmed live against a real Jobvite posting,
# NinjaOne): its "Add Resume" widget's real <input type=file> sits inside a
# `#attachmentDropdown` wrapper with 25 descendants (well above the
# tolerance above, correctly, since this genuinely IS a hidden, currently-
# inactive dropdown MENU - not a widget-hiding detail) - the file input
# only becomes reachable after clicking a "Select" button, which reveals a
# menu of upload-source choices ("My Computer" / Dropbox / Google Drive),
# one of which must itself be clicked before the file input is truly
# interactable. This is a materially different pattern from every
# "click Select" file-upload variant confirmed so far this session (a
# single-step reveal, not a two-step click-through-a-menu one), and
# upload_document/_find_genuinely_present_file_inputs have no notion of
# "click through a reveal menu first" - correctly refusing to guess at an
# unfamiliar multi-step widget rather than attempting a fragile blind
# click sequence, this surfaces as a required-field validation failure
# ("Please provide this information.") blocking progression, not a false
# success. Deliberately not attempted here - a real fix needs adapter
# logic that recognizes and clicks through a menu-reveal step before
# calling set_input_files, which no confirmed-live pattern so far has
# actually required.

_ANCESTORS_VISIBLE_JS = f"""
el => {{
    let node = el.parentElement;
    while (node) {{
        const style = window.getComputedStyle(node);
        const isHidden = style.display === 'none' || style.visibility === 'hidden';
        if (isHidden && node.querySelectorAll('*').length > {_MAX_TOLERATED_HIDDEN_WRAPPER_DESCENDANTS}) {{
            return false;
        }}
        node = node.parentElement;
    }}
    return true;
}}
"""
# Strips a trailing required-field marker (e.g. Lever's "✱", a plain "*")
# that's concatenated directly into the label div's text content.
_TRAILING_REQUIRED_MARKER_RE = re.compile(r"[✱*]+\s*$")

# Parses one line of Locator.aria_snapshot()'s output, e.g.:
#   - textbox "First name": Brian
#   - checkbox "I agree" [checked]
#   - button "Next"
# See _accessibility_nodes for why this (rather than the removed
# Page.accessibility.snapshot() dict-tree API) is what's used.
_ARIA_SNAPSHOT_LINE_RE = re.compile(r'^-\s+([a-zA-Z][\w-]*)\s+"([^"]*)"(?:\s+\[([^\]]*)\])?(?::\s?(.*))?$')

# Confirmed live against a real SmartRecruiters "OneClick" apply form: it's
# built entirely from custom Web Components (oc-input, spl-input, oc-button,
# spl-autocomplete, ...) whose real, fillable <input>/<textarea> elements
# live one level inside *open* shadow DOM. Every field/button-discovery
# query in this file up to this point (page.query_selector_all("input:
# visible, ..."), document.querySelectorAll in the JS signal snippets)
# found nothing on that page - not because of a settle-timing issue (the
# same queries still found nothing well after the page had visibly finished
# rendering, screenshot and accessibility-snapshot confirmed), but because
# they simply cannot see past the shadow boundary. `Locator.aria_snapshot()`
# does cross shadow-DOM boundaries (confirmed live and by test), which is
# what makes this fallback work at all. Used as a fallback, not a
# replacement: gated behind "the CSS-based scan found nothing", so it adds
# no behavior change (and no per-iteration cost) on every previously-
# confirmed-working platform (Greenhouse/Lever/Ashby/Workday/Epic), which
# all expose real native form elements in light DOM.
#
# KNOWN GAP, NOT fixed by this fallback (confirmed live against a real
# iCIMS posting, careers-gdms.icims.com): unlike shadow DOM,
# `page.locator("body").aria_snapshot()` does NOT descend into a same-page
# <iframe>'s content - iCIMS renders its ENTIRE apply form (and, per
# render_server.py's own iframe fix, its entire job description) inside
# one. _gather_signals/_find_visible_form/inspect_form/fill_field/
# upload_document/_find_button_by_words are all written in terms of a
# single `page` (or an ElementHandle scoped to it) throughout this file;
# none of them ever look inside a child Frame. Confirmed the run pauses as
# UNKNOWN/unsupported_flow on iCIMS's real apply page with
# visible_field_count == 0 despite this fallback being active - the
# accessibility-tree approach alone doesn't solve the iframe case the way
# it solves the shadow-DOM case. Properly fixing this means threading
# frame-awareness through every one of the methods above (which frame is
# "the" form currently live in, and operating fill/upload/click calls
# against that Frame rather than always against `page`) - a materially
# larger change than this fallback, deliberately not attempted here rather
# than ship something partial/untested against a real site.
_ACCESSIBILITY_FIELD_ROLES = {"textbox", "searchbox", "combobox", "spinbutton"}
_ACCESSIBILITY_CHOICE_ROLES = {"checkbox", "radio"}
_ACCESSIBILITY_BUTTON_ROLES = {"button", "link"}


class GenericAdapter(ATSAdapter):
    """Fallback adapter for unknown ATS systems.

    Unlike MockATSAdapter (which can key off this one site's known routing),
    every selector/signal here is generic - no assumption about class names,
    URL structure, or hash routing belonging to any specific ATS. Playwright's
    `:visible` pseudo-class does the DOM-scoping work that a site-specific
    adapter would otherwise need explicit container selectors for (the exact
    class of bug found twice in MockATSAdapter this session - grabbing the
    first same-named element in the DOM regardless of whether it's the one
    actually on screen).
    """

    def __init__(self):
        self._last_detection_reasoning: dict = {}

    async def detect(self, page: Page) -> bool:
        """Always returns True as fallback"""
        return True

    async def _accessibility_nodes(self, page: Page) -> List[dict]:
        """Flattened accessibility tree (role + name + value/checked per
        node) - see the module-level comment above _ACCESSIBILITY_FIELD_ROLES
        for why this exists. Empty list on any failure (e.g. page
        mid-navigation) rather than raising - every caller treats this as a
        best-effort fallback source, not a required one.

        `Page.accessibility.snapshot()` (the API this was originally written
        against) doesn't exist in the Playwright version actually installed
        here (1.61 - it was removed some versions back in favor of
        Locator.aria_snapshot()), which meant this silently returned []
        every time via the except-Exception branch, without a single
        currently-affected platform ever surfacing an error - confirmed
        live: SmartRecruiters' apply form still showed zero discovered
        fields after switching to the modern API, which is what led to
        finding the *real*, separate blocker (a DataDome challenge, see
        captcha_detection.py) rather than this being the last word on why.
        aria_snapshot() returns a YAML-ish tree as one string, not a
        dict - each field/button line looks like:
            - textbox "First name": Brian
            - checkbox "I agree" [checked]
        parsed by _ARIA_SNAPSHOT_LINE_RE below. No `required` info is
        exposed this way (confirmed: a real required-attribute input's
        accessible name in this format carries no marker for it, and the
        visible "*" seen on a real SmartRecruiters label is a separate
        sibling text node, not part of the field's own accessible name) -
        every field built from this fallback defaults required=False.
        """
        try:
            snapshot = await page.locator("body").aria_snapshot()
        except Exception:
            return []
        nodes: List[dict] = []
        for line in snapshot.splitlines():
            match = _ARIA_SNAPSHOT_LINE_RE.match(line.strip())
            if not match:
                continue
            role, name, flags, value = match.groups()
            name = (name or "").strip()
            if not name:
                continue
            nodes.append({
                "role": role,
                "name": name,
                "checked": "checked" in (flags or ""),
                "value": (value or "").strip(),
            })
        return nodes

    @staticmethod
    def _is_accessibility_node_filled(node: dict) -> bool:
        if node.get("role") in _ACCESSIBILITY_CHOICE_ROLES:
            return bool(node.get("checked"))
        return bool((node.get("value") or "").strip())

    @staticmethod
    def _slugify(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_") or "field"

    @staticmethod
    def _role_selector(role: str, name: str) -> str:
        """Playwright's built-in `role=` selector engine - accessibility-
        tree based (like _accessibility_nodes above), so it resolves the
        same shadow-DOM-nested element the snapshot found it from. Passed
        straight into the existing page.fill()/check()/set_input_files()
        calls elsewhere in this file, which accept any Playwright selector
        string - no change needed to the filling code itself."""
        escaped = name.replace('"', '\\"').replace("\n", " ")
        return f'role={role}[name="{escaped}" i]'

    async def _find_visible_form(self, page: Page) -> Optional[ElementHandle]:
        form = await page.query_selector("form:visible")
        if form:
            return form
        # Many modern SPA-based ATS application pages don't use a semantic
        # <form> at all - confirmed live against a real Ashby posting: zero
        # <form> elements anywhere on the page, but 11 real, fillable
        # visible inputs sitting in plain <div>s (fields submitted via
        # fetch/JS from component state, not native form submission).
        # Falling back to the whole visible body as the field-scanning
        # container means those still get found, instead of every
        # field-filling handler unconditionally raising on any such page.
        return await page.query_selector("body")

    async def _resolve_label(self, page: Page, input_elem: ElementHandle, input_id: Optional[str]) -> Optional[str]:
        """<label for=id> first, then aria-labelledby, then the DOM-sibling
        fallback, cleaned of a trailing required-marker - shared by every
        field type (including each option inside a radio group, where it
        resolves that option's own choice text rather than the group's
        question).

        Confirmed live against a real Rippling posting (Just Appraised):
        every field's own `name`/`id` is a fully random, opaque string
        (e.g. "8PpiPJq9jw") with zero semantic relationship to what the
        field actually asks - no <label for=id>, and the real label text
        sits several DOM levels away from the input (not a sibling this
        adapter's existing fallback pattern would find), connected only
        via `aria-labelledby="field-12-label"` pointing at a
        `<span id="field-12-label">First name</span>` elsewhere in the
        tree. This is itself a first-class, standard accessible-labeling
        mechanism (not a hack), just one this adapter never checked -
        without it, every field's label fell through to inspect_form's
        last-resort raw-identifier prettification, showing an opaque
        machine-generated string (e.g. "Lj51Rek51Zx") as the question text
        a human would need to answer.
        """
        try:
            resolved = None
            if input_id:
                label_elem = await page.query_selector(f'label[for="{input_id}"]')
                if label_elem:
                    resolved = await label_elem.text_content()
            if not resolved:
                labelledby_id = await input_elem.get_attribute("aria-labelledby")
                if labelledby_id:
                    # aria-labelledby can reference multiple space-separated
                    # IDs, concatenated in order per the ARIA spec - real
                    # sites (confirmed live: Rippling splits "First name"
                    # and its "*" required-marker into two separate spans)
                    # routinely use more than one.
                    parts = []
                    for ref_id in labelledby_id.split():
                        # Attribute selector, not a `#id` CSS ID selector -
                        # real-world IDs (confirmed live: Rippling's own
                        # "field-12-label") can start with characters or
                        # contain patterns that need escaping as a CSS ID
                        # selector; matching by attribute value sidesteps
                        # that entirely.
                        ref_elem = await page.query_selector(f'[id="{ref_id}"]')
                        if ref_elem:
                            text = (await ref_elem.text_content()) or ""
                            if text.strip():
                                parts.append(text.strip())
                    if parts:
                        resolved = " ".join(parts)
            if not resolved:
                resolved = await input_elem.evaluate(_SIBLING_LABEL_JS)
            if resolved:
                cleaned = _TRAILING_REQUIRED_MARKER_RE.sub("", resolved).strip()
                return cleaned or None
        except Exception:
            pass
        return None

    async def _find_genuinely_present_file_inputs(self, scope) -> List[ElementHandle]:
        """Every file input that's actually part of what's on screen right
        now - :visible ones, plus ones hidden only by their own styling
        (see _ANCESTORS_VISIBLE_JS's docstring for why that distinction
        matters). Shared by inspect_form and _gather_signals so both agree
        on what "a file input is present" means."""
        found = []
        for file_input in await scope.query_selector_all("input[type='file']"):
            if await file_input.is_visible():
                found.append(file_input)
                continue
            if await file_input.evaluate(_ANCESTORS_VISIBLE_JS):
                found.append(file_input)
        return found

    @staticmethod
    async def _is_required(elem) -> bool:
        """A field can be required via the native HTML `required` boolean
        attribute, or via `aria-required="true"` alone with no `required`
        attribute at all - confirmed live on a real Greenhouse posting,
        whose React-based custom question widgets only ever set
        aria-required (the visible "*" in the label is a separate,
        decorative <span>, not tied to either attribute). Checking only
        `required` silently treated a real required field as optional,
        so it was never a candidate for the "ask AI to answer this
        required field" fallback and was skipped forever."""
        if await elem.get_attribute("required") is not None:
            return True
        return (await elem.get_attribute("aria-required") or "").lower() == "true"

    async def inspect_form(self, page: Page) -> ApplicationForm:
        """Extract generic form schema from whichever form is actually visible"""
        fields = []
        # Radio buttons share one `name` per group and only make sense as a
        # single choice-of-N field (mirroring how <select> already works),
        # not as N separate same-named fields each independently "filled" -
        # collected here and added once after the main loop. Confirmed live
        # against a real Ashby posting: a "willing to relocate?" question
        # rendered as two real <input type=radio> options, which the main
        # loop's generic `page.fill()` fallback can't fill at all (fill()
        # only works on text-like inputs), so the field was silently
        # skipped every single pass, forever - a real, blocking gap for a
        # question shape this common.
        radio_groups: dict = {}

        form = await self._find_visible_form(page)
        if not form:
            raise ValueError("No visible form found on page")

        # File inputs are queried separately (via
        # _find_genuinely_present_file_inputs, excluded here to avoid
        # double-adding one that's already :visible) - not just near-zero
        # geometry like Ashby's 1x1 pattern, but genuinely display:none
        # with a separate visible label/button triggering it (confirmed
        # live against Epic's real Avature-hosted careers portal).
        inputs = await form.query_selector_all("input:visible:not([type='file']), select:visible, textarea:visible")
        inputs.extend(await self._find_genuinely_present_file_inputs(form))

        # Shadow-DOM fallback - see _ACCESSIBILITY_FIELD_ROLES. Combobox
        # (e.g. a location autocomplete) is treated as plain text, not a
        # native <select>: these are typically typeahead widgets accepting
        # free text, not a fixed enumerable option list, and confirmed live
        # (SmartRecruiters' "City" field) to be a real <input> under the
        # custom element - page.fill() works on it the same as any textbox.
        if not inputs:
            for node in await self._accessibility_nodes(page):
                role = node.get("role")
                name = (node.get("name") or "").strip()
                if not name:
                    continue
                if role in _ACCESSIBILITY_FIELD_ROLES:
                    input_type = "text"
                elif role in _ACCESSIBILITY_CHOICE_ROLES:
                    input_type = role
                else:
                    continue
                fields.append(
                    FormField(
                        # aria_snapshot() carries no `required` info (see
                        # _accessibility_nodes) - defaults False, a known
                        # simplification of this fallback path.
                        name=self._slugify(name),
                        label=name,
                        input_type=input_type,
                        required=False,
                        options=None,
                        placeholder=None,
                        selector=self._role_selector(role, name),
                    )
                )

        for input_elem in inputs:
            name = await input_elem.get_attribute("name")
            input_id = await input_elem.get_attribute("id")

            if not name and not input_id:
                continue

            if not await is_genuinely_fillable(input_elem):
                continue

            identifier = name or input_id
            input_type = await input_elem.get_attribute("type") or "text"
            tag_name = await input_elem.evaluate("el => el.tagName.toLowerCase()")

            if tag_name == "select":
                input_type = "select"
            elif tag_name == "textarea":
                input_type = "textarea"

            if input_type in ["submit", "button"]:
                continue

            if input_type == "radio":
                if not name:
                    continue  # can't group same-choice radios without a shared name
                option_label = await self._resolve_label(page, input_elem, input_id)
                group = radio_groups.setdefault(name, {"options": [], "required": False})
                if option_label and option_label not in group["options"]:
                    group["options"].append(option_label)
                if await self._is_required(input_elem):
                    group["required"] = True
                continue

            required = await self._is_required(input_elem)
            placeholder = await input_elem.get_attribute("placeholder")
            label_text = await self._resolve_label(page, input_elem, input_id) or identifier.replace("_", " ").replace("-", " ").title()

            options = None
            if input_type == "select":
                option_elems = await input_elem.query_selector_all("option")
                options = []
                for opt in option_elems:
                    value = await opt.get_attribute("value")
                    if not value:
                        continue
                    # The option's human-readable text, not its `value`
                    # attribute - real ATS's routinely use an opaque
                    # numeric/UUID value with the actual meaning only in
                    # the text content (confirmed live: Epic's real
                    # Avature-hosted careers portal has
                    # value="28074">Bachelor's Degree...). Matching
                    # against raw IDs like "28074" meant an agent's or a
                    # human's answer could never confidently map to any
                    # select on such a site - every constrained-choice
                    # question deferred to the user regardless of how
                    # good the answer was, even an exact, previously-
                    # approved one. fill_field selects by this same label
                    # text now, not by value.
                    text = (await opt.text_content() or "").strip()
                    options.append(text or value)

            selector = f'[name="{name}"]' if name else f'#{input_id}'

            fields.append(
                FormField(
                    name=identifier,
                    label=label_text.strip() if label_text else identifier,
                    input_type=input_type,
                    required=required,
                    options=options,
                    placeholder=placeholder,
                    selector=selector,
                )
            )

        for group_name, group in radio_groups.items():
            if not group["options"]:
                continue
            first_radio = await form.query_selector(f'input[type="radio"][name="{group_name}"]')
            question_label = group_name.replace("_", " ").title()
            if first_radio:
                try:
                    resolved = await first_radio.evaluate(
                        """el => {
                            const fs = el.closest('fieldset');
                            if (!fs) return null;
                            const legend = fs.querySelector('legend, label');
                            return legend ? legend.textContent.trim() : null;
                        }"""
                    )
                    if resolved:
                        question_label = _TRAILING_REQUIRED_MARKER_RE.sub("", resolved).strip() or question_label
                except Exception:
                    pass
            fields.append(
                FormField(
                    name=group_name,
                    label=question_label,
                    input_type="radio",
                    required=group["required"],
                    options=group["options"],
                    placeholder=None,
                    selector=f'input[type="radio"][name="{group_name}"]',
                )
            )

        submit_btn = await form.query_selector('[type="submit"]:visible')
        submit_text = "Submit"
        if submit_btn:
            submit_text = await submit_btn.text_content() or "Submit"

        return ApplicationForm(
            page_number=1,
            total_pages=1,
            fields=fields,
            submit_button_text=submit_text.strip(),
        )

    async def fill_field(self, page: Page, field: FormField, value: str) -> FillResult:
        """Fill a single field"""
        try:
            selector = field.selector

            if field.input_type == "select":
                # By label, not value - field.options now holds each
                # option's human-readable text (see inspect_form), since
                # a real site's `value` attribute is routinely an opaque
                # ID with no relationship to what an answer would ever
                # contain.
                await page.select_option(selector, label=value)
            elif field.input_type == "textarea":
                await page.fill(selector, value)
                error = await self._verify_fill_took_effect(page, selector, value, field.name)
                if error:
                    return error
            elif field.input_type == "checkbox":
                # KNOWN GAP, NOT root-caused here: confirmed live against a
                # real Pinpoint posting (Confluence Technologies), a
                # required consent checkbox ("Allow us to process your
                # personal information") remained visibly unchecked in a
                # later checkpoint screenshot despite an "answered_question"
                # cycle resolving "Yes" for it (which should reach this
                # branch and call page.check()). A plain page.check()/
                # manual click on the same live checkbox worked correctly
                # in isolation, so the checkbox itself isn't the problem -
                # something about the field/selector identity between when
                # the question was asked and when this code re-resolves and
                # re-fills it is the more likely suspect (matches this
                # site's earlier-confirmed pattern of using fully
                # client-rendered, possibly re-mounted form sections - see
                # this file's Rippling/aria-labelledby comment for a
                # related but distinct labeling issue on the same class of
                # site). The run correctly stalled and escalated rather
                # than reporting false success, so this didn't risk a
                # submission with a missing required consent - left as an
                # observed, not-yet-root-caused gap rather than guessing at
                # a fix without being able to reproduce the exact failure
                # live.
                if str(value).strip().lower() in ("true", "1", "yes", "on"):
                    await page.check(selector)
                else:
                    await page.uncheck(selector)
            elif field.input_type == "file":
                return FillResult(
                    success=False,
                    field=field.name,
                    error="Use upload_document for file fields",
                )
            elif field.input_type == "radio":
                # `value` is one of field.options (an option's own choice
                # text, resolved the same way select's option values are
                # matched) - find the specific radio in the group whose
                # own label matches it and check that one. page.fill()
                # (the generic fallback below) can't fill a radio at all;
                # before this, every radio-group question silently failed
                # to fill, forever, on every real ATS that uses one.
                radios = await page.query_selector_all(selector)
                matched = False
                for radio in radios:
                    radio_id = await radio.get_attribute("id")
                    option_label = await self._resolve_label(page, radio, radio_id)
                    if option_label == value:
                        await radio.check()
                        matched = True
                        break
                if not matched:
                    return FillResult(success=False, field=field.name, error=f"No radio option matching {value!r}")
            else:
                await page.fill(selector, value)
                error = await self._verify_fill_took_effect(page, selector, value, field.name)
                if error:
                    return error

            logger.info(f"Filled field {field.name}")
            return FillResult(success=True, field=field.name, value=value)

        except Exception as e:
            logger.error(f"Error filling field {field.name}: {e}")
            return FillResult(success=False, field=field.name, error=str(e))

    # KNOWN GAP, NOT fixed here: _verify_fill_took_effect below only catches
    # a field ending up EMPTY, not a field ending up NON-empty but WRONG.
    # Confirmed live against the same real Recruitee posting (TYTAN
    # Technologies) that motivated that check: its phone field is a custom
    # live-formatting widget, not a plain <input type=tel> - it starts
    # pre-filled with a country-code default ("+49", the site's German
    # locale) and re-parses a country code from whatever's typed as it's
    # typed. Filling Brian's real US number "646-236-7795" over that
    # default produced "+64 6 236 7795" (New Zealand) - the widget's live
    # parser matched "64" out of the "646" area code as a country-code
    # candidate before "646" could ever be read as a single area-code
    # unit, splitting it into a wrong country prefix plus a stray leading
    # digit. Reproduced via plain browser interaction (not a Playwright-
    # automation-specific quirk), and confirmed this is genuinely how a
    # real Recruitee phone field behaves for any NANP number sharing
    # digits with an existing country code. A general fix needs actual
    # phone-number verification (does the resulting value's digits still
    # correspond to the intended number, independent of formatting/country
    # prefix) - not attempted here, since a naive version risks false-
    # positive-flagging legitimately-different-but-correct formatting
    # (e.g. a site normalizing "646-236-7795" to "+1 646 236 7795").
    @staticmethod
    async def _verify_fill_took_effect(page: Page, selector: str, intended_value: str, field_name: str) -> Optional[FillResult]:
        """page.fill() raises on a genuinely disabled/detached element, but
        NOT when a native input's own type constraint (type=number,
        type=date, ...) rejects text that doesn't match its expected
        format - the browser just silently leaves the field empty, no
        exception, no console error, nothing. Confirmed live against a
        real Recruitee posting: a "What is your salary expectation?"
        question rendered as <input type="number">, and an entirely
        reasonable free-text answer ("Negotiable, based on role scope and
        total compensation") silently produced an empty required field -
        fill_field reported success, ctx.filled_fields recorded it as
        done, and the run moved on genuinely believing a required field
        was filled when it was blank. The same failure mode hit a
        type="date" field asked in free text ("Immediately") moments
        later on the same form. Reading the value back and comparing
        against what was intended turns this from a silent, invisible gap
        into an honest FillResult failure - the field stays correctly
        marked unfilled, so has_unfilled_visible_field keeps blocking
        SUBMIT_READY, and the run eventually escalates for a human to
        provide a format the input will actually accept, rather than
        silently reporting a required field as done when it never
        received a value at all."""
        if not intended_value.strip():
            return None
        try:
            actual_value = await page.input_value(selector)
        except Exception:
            # Not every element input_value() supports (e.g. contenteditable)
            # raises here - best-effort verification only, not required for
            # every possible field shape this adapter's generic path meets.
            return None
        if actual_value.strip():
            return None
        return FillResult(
            success=False,
            field=field_name,
            error=(
                f"page.fill() reported success but the field is still empty - the input's own "
                f"format constraint (e.g. type=number, type=date) likely rejected {intended_value!r}"
            ),
        )

    async def upload_document(
        self, page: Page, field: FormField, file_path: str
    ) -> UploadResult:
        """Upload file"""
        try:
            await page.set_input_files(field.selector, file_path)
            logger.info(f"Uploaded file to {field.name}")
            return UploadResult(success=True, field=field.name, file_path=file_path)

        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return UploadResult(
                success=False, field=field.name, file_path=file_path, error=str(e)
            )

    async def _find_button_by_words(self, page: Page, words: Tuple[str, ...], scope=None) -> Optional[ElementHandle]:
        """`scope` narrows the search to within a specific container (e.g.
        the actual <form> being filled) instead of the whole page -
        matters for a word list like ("log in", "sign in") that's likely
        to also match an unrelated persistent header/nav link appearing
        earlier in DOM order than the form's own submit control. Defaults
        to `page` (whole-page search) for callers that don't have - or
        don't need - a narrower container."""
        container = scope or page
        candidates = await container.query_selector_all(
            "button:visible, input[type='submit']:visible, input[type='button']:visible, a:visible"
        )
        for el in candidates:
            text = ((await el.text_content()) or (await el.get_attribute("value")) or "").strip().lower()
            if text and any(word in text for word in words):
                return el
        # Shadow-DOM fallback - see _ACCESSIBILITY_FIELD_ROLES. Only when no
        # narrower `scope` was requested: the accessibility tree here is
        # always walked from the whole page (Locator.aria_snapshot() has no
        # equivalent of an ElementHandle-scoped query in this codebase's
        # usage), so honoring `scope`'s whole reason for existing - keeping
        # a page-wide word list like ("log in", "sign in") from matching an
        # unrelated header/nav link instead of the form's own control -
        # means skipping this fallback entirely whenever a caller actually
        # asked for that narrowing (confirmed by a real regression: this
        # unconditionally matched the header's "log in" link even when
        # scoped to a form with no such control at all). Every current
        # caller that needs the shadow-DOM fallback (navigate_next, the
        # submit-button lookup, _handle_landing's apply click) calls this
        # unscoped anyway.
        if scope is not None:
            return None
        for node in await self._accessibility_nodes(page):
            if node.get("role") not in _ACCESSIBILITY_BUTTON_ROLES:
                continue
            name = (node.get("name") or "").strip()
            if not name or not any(word in name.lower() for word in words):
                continue
            try:
                handle = await page.get_by_role(node["role"], name=name, exact=True).first.element_handle()
            except Exception:
                continue
            if handle:
                return handle
        return None

    async def navigate_next(self, page: Page) -> NavigationResult:
        """Generic next/continue: find a plausibly-labeled control, click it,
        and confirm the page actually changed (not just that the click landed) -
        the same lesson MockATSAdapter's navigate_next bug taught this session,
        applied generically instead of via a known selector."""
        try:
            before_url = page.url
            before_text = await page.text_content("body")

            # _ADVANCE_BUTTON_WORDS, not just _NEXT_BUTTON_WORDS - this
            # method's only caller (_handle_application_page) already
            # checked existence with the broader list before calling here;
            # searching with a narrower list here would just silently fail
            # to find the same "I Accept"-worded control again.
            next_btn = await self._find_button_by_words(page, _ADVANCE_BUTTON_WORDS)
            if next_btn is None:
                return NavigationResult(success=False, page_number=1, url=page.url, error="No next/continue control found")

            await next_btn.click()
            await page.wait_for_timeout(500)

            after_url = page.url
            after_text = await page.text_content("body")
            if after_url == before_url and after_text == before_text:
                return NavigationResult(success=False, page_number=1, url=page.url, error="Page did not change after clicking next/continue")

            return NavigationResult(success=True, page_number=1, url=page.url)

        except Exception as e:
            logger.error(f"Error navigating: {e}")
            return NavigationResult(success=False, page_number=1, url=page.url, error=str(e))

    async def submit(self, page: Page) -> SubmissionResult:
        """Final submit"""
        try:
            submit_btn = await self._find_button_by_words(page, _SUBMIT_BUTTON_WORDS)
            if not submit_btn:
                return SubmissionResult(success=False, error="Submit button not found")

            current_url = page.url
            await submit_btn.click()
            await page.wait_for_timeout(2000)

            new_url = page.url
            logger.info(f"Submitted form, URL: {current_url} -> {new_url}")

            return SubmissionResult(success=True, redirect_url=new_url)

        except Exception as e:
            logger.error(f"Error submitting: {e}")
            return SubmissionResult(success=False, error=str(e))

    @staticmethod
    async def _visible_body_text(page: Page) -> str:
        """document.body.textContent (what page.text_content("body") uses
        under the hood) includes the text content of <script> and <style>
        elements, not just genuinely visible page text - a modern React/
        Next.js SPA routinely embeds a full JSON hydration payload in a
        <script> tag containing templates/config for states the user isn't
        even looking at. Confirmed live on a real Ashby posting: its
        hydration payload contains the literal post-submission message
        ("applicationSubmittedSuccessMessage": "Thank you for applying...")
        on the ordinary, pre-submission landing page, which was enough on
        its own (plus an unrelated "confirmation" substring inside an
        internal JSON key name, appConfirmationTrackingPixelHtml) to clear
        detect_confirmation's threshold and report the application as
        successfully submitted and confirmed before the automation had
        filled in a single field."""
        return await page.evaluate(
            """() => {
                const clone = document.body.cloneNode(true);
                clone.querySelectorAll('script, style').forEach(el => el.remove());
                return clone.textContent || '';
            }"""
        )

    async def detect_confirmation(self, page: Page) -> ConfirmationResult:
        """Generic confirmation detection.

        CRITICAL, confirmed live against a real Jobvite posting (NinjaOne):
        this used to accumulate 0.3 confidence per matched keyword from a
        list including bare "thank you" and bare "confirmation", with a
        0.5 threshold - meaning ANY TWO of these generic, unrelated-prose-
        friendly words appearing ANYWHERE in the page's visible text was
        enough to report a full submission, with zero other corroborating
        evidence (no check that a submit button was ever clicked, no check
        that any application field was ever filled). A real NinjaOne
        candidate consent page's privacy-policy legal text plainly
        contains both - "Thank you for considering a job opportunity..."
        and "...you may have received a confirmation email..." - and nei-
        ther "I Accept" nor "I Decline" had even been clicked yet. This is
        the exact class of bug this session already found and partially
        fixed once before (see _visible_body_text's docstring, a real
        Ashby posting whose hydration payload leaked equivalent generic
        keywords) - that fix addressed one SOURCE of leaked text
        (script/style content), not the underlying fragility of matching
        generic, common-English words/short-phrases against an unbounded
        block of genuinely visible but entirely unrelated prose (a job
        description, a privacy policy, terms of service - any of which
        can plausibly contain "thank you" or "confirmation" in ordinary,
        non-submission-related sentences).

        Fixed by replacing every generic keyword with a specific, multi-
        word phrase a real confirmation page uses and essentially no
        unrelated real-world document would ("thank you for applying",
        not bare "thank you") - each phrase is now precise enough that a
        single match is trusted outright, rather than needing several
        weak signals to combine into a false positive.
        """
        try:
            body_text = await self._visible_body_text(page)
            body_lower = body_text.lower()

            confirmation_phrases = [
                "thank you for applying",
                "thank you for your application",
                "thank you for submitting your application",
                "your application has been submitted",
                "your application was submitted",
                "application submitted successfully",
                "we have received your application",
                "we've received your application",
                "application received successfully",
                "your application has been received",
            ]

            matched = any(phrase in body_lower for phrase in confirmation_phrases)
            confidence = 0.9 if matched else 0.0
            confirmed = matched

            if confirmed:
                logger.info(f"Detected possible confirmation page (confidence: {confidence})")

            return ConfirmationResult(
                confirmed=confirmed,
                confidence=confidence,
                message="Generic confirmation detection",
            )

        except Exception as e:
            logger.error(f"Error detecting confirmation: {e}")
            return ConfirmationResult(confirmed=False, confidence=0.0)

    def get_name(self) -> str:
        return "Generic"

    # -- State machine layer: signal-scoring detection, generic handlers --

    async def _gather_signals(self, page: Page) -> dict:
        url = page.url.lower()

        heading_els = await page.query_selector_all("h1:visible, h2:visible")
        headings = [((await el.text_content()) or "").strip().lower() for el in heading_els]

        button_els = await page.query_selector_all(
            "button:visible, input[type='submit']:visible, input[type='button']:visible, a:visible"
        )
        buttons: List[str] = []
        # Confirmed live against a real Duke University (SuccessFactors)
        # posting: distinguishes an Apply CTA that's a genuine navigation
        # to a different page (Duke's own /talentcommunity/apply/... URL,
        # like nearly every real ATS) from one that's a same-page anchor/
        # JS scroll-to-form (the real Greenhouse case that originally
        # motivated _score_landing's incidental-fields penalty below - see
        # that comment). Only the latter means unrelated fields elsewhere
        # on the page (a site search box, a job-alert-subscription widget -
        # both confirmed live on this same Duke page, neither related to
        # the application) should count against a LANDING classification;
        # for a real cross-page Apply link, those fields are just page
        # furniture and irrelevant to whether this is still the landing
        # page.
        apply_link_is_cross_page = False
        for el in button_els:
            text = ((await el.text_content()) or (await el.get_attribute("value")) or "").strip().lower()
            if text:
                buttons.append(text)
            if any(w in text for w in _APPLY_BUTTON_WORDS):
                href = await el.get_attribute("href")
                if href and not href.startswith("#") and not href.lower().startswith("javascript:"):
                    apply_link_is_cross_page = True

        has_password = (await page.query_selector("input[type='password']:visible")) is not None
        has_confirm_password = (await page.query_selector("input[name*='confirm' i][type='password']:visible")) is not None
        has_file_input = bool(await self._find_genuinely_present_file_inputs(page))
        # A widget offering to "Replace" a file means one was already
        # attached - the underlying <input type=file> can stay in the DOM
        # either way (confirmed live against a real Ashby posting), so
        # has_file_input alone can't distinguish "empty, needs uploading"
        # from "already uploaded". Without this, resume_upload keeps
        # re-triggering the same upload forever, and _score_application's
        # `not has_file_input` gate never passes even once the resume is
        # genuinely attached - the run never reaches the rest of the form.
        resume_already_attached = any("replace" in b for b in buttons)
        visible_fields = await page.query_selector_all("input:visible, select:visible, textarea:visible")
        # Distinct from visible_field_count: excludes file inputs, so it
        # answers "are there substantive fields to fill" independent of
        # whether a resume/cover-letter upload widget also happens to be on
        # the page. Needed because real single-page ATS forms (confirmed
        # live against a real Greenhouse posting) render the file input
        # alongside every other field from the very first load - there is
        # no separate "resume upload" page to visit first, so gating
        # anything on has_file_input being False can never pass, and the
        # page can never be recognized as a fillable form at all.
        non_file_fields = await page.query_selector_all(
            "input:visible:not([type=file]), select:visible, textarea:visible"
        )
        # Field *presence* alone isn't evidence of readiness to submit - a
        # single-page application form shows its real "Submit Application"
        # button from the moment it renders, before a single field has been
        # touched. Requires actual non-empty values, not just that inputs
        # exist, as further defense alongside visible_field_count for the
        # single most dangerous misclassification this adapter can make.
        has_any_filled_field = await page.evaluate(
            """() => {
                const hasTypedValue = Array.from(document.querySelectorAll(
                    "input:not([type=file]):not([type=checkbox]):not([type=radio]):not([type=hidden]), textarea"
                )).some(el => el.offsetParent !== null && el.value && el.value.trim().length > 0);
                if (hasTypedValue) return true;
                // A review page can legitimately have nothing left but a
                // consent checkbox (the actual data was filled on earlier
                // pages, no longer visible) - checking it is itself real
                // evidence of interaction, not just presence.
                return Array.from(document.querySelectorAll(
                    "input[type=checkbox]:checked, input[type=radio]:checked"
                )).some(el => el.offsetParent !== null);
            }"""
        )
        # The counterpart to has_any_filled_field: is there still a real,
        # empty, fillable field on the page? Without this, a single-page
        # form that's partially filled ties APPLICATION against
        # SUBMIT_READY every single loop (both score 0.5) - APPLICATION
        # wins the tie (by design, the safe side), but nothing ever
        # actually changes between iterations once the same fields resolve
        # to the same values each time, so the run just re-fills the same
        # data forever until MAX_TRANSITIONS gives up. Confirmed live
        # against a real Ashby posting: exhausted all 40 transitions stuck
        # on APPLICATION despite every resolvable field already being
        # filled correctly.
        #
        # KNOWN GAP (confirmed live on a real Greenhouse posting, not fixed
        # here): this counts ANY empty visible field, including an
        # optional one nothing in the candidate's data can fill (e.g. an
        # optional "Website" field) - so a form with even one such field
        # can never reach SUBMIT_READY at all, and re-runs its full fill
        # pass (including a real, billed AI call per AI-answered question)
        # every loop until MAX_TRANSITIONS gives up. Tried scoping this to
        # required-marked fields only, but that regressed a deliberate
        # safety test (test_generic_adapter_partial_fill_no_deadlock.py) -
        # an empty `email` input with no `required` attribute at all must
        # still block SUBMIT_READY, so "is this field required" can't be
        # answered by the DOM's `required`/`aria-required` markup alone.
        # Reverted rather than ship a version that passed CI but weakened a
        # real safety property; needs the Python-side "does the candidate
        # actually have data for this field" check (already computed by
        # resolve_field_value) threaded into this signal, not a bigger
        # DOM-only regex. Confirmed live a second time against a real
        # Teamtailor posting (SOFTSWISS): an optional, empty "cover_letter"
        # textarea (no data for it, nothing required about it) blocked
        # SUBMIT_READY the same way - stall-detected and escalated
        # correctly rather than a false success, exactly the safe fallback
        # this gap was left with. Still not fixed - the stall detector,
        # not this signal, is what's actually protecting these runs.
        has_unfilled_visible_field = await page.evaluate(
            """() => Array.from(document.querySelectorAll(
                "input:not([type=file]):not([type=checkbox]):not([type=radio]):not([type=hidden]), select, textarea"
            )).some(el => el.offsetParent !== null && (!el.value || el.value.trim().length === 0))"""
        )

        unchecked_required_checkbox = False
        for cb in await page.query_selector_all("input[type='checkbox'][required]:visible"):
            if not await cb.is_checked():
                unchecked_required_checkbox = True
                break

        # Shadow-DOM fallback - see _ACCESSIBILITY_FIELD_ROLES. Gated on
        # non_file_fields being empty so every already-confirmed-working
        # platform (real native inputs in light DOM) pays zero extra cost
        # and sees zero behavior change - this only activates on a page
        # where the CSS-based scan above found nothing at all.
        role_field_count = 0
        if not non_file_fields:
            role_nodes = await self._accessibility_nodes(page)
            role_button_names = [
                (n.get("name") or "").strip().lower()
                for n in role_nodes
                if n.get("role") in _ACCESSIBILITY_BUTTON_ROLES
            ]
            buttons = list(dict.fromkeys(buttons + [n for n in role_button_names if n]))
            role_field_nodes = [
                n for n in role_nodes
                if n.get("role") in _ACCESSIBILITY_FIELD_ROLES | _ACCESSIBILITY_CHOICE_ROLES
            ]
            role_field_count = len(role_field_nodes)
            if role_field_nodes:
                has_any_filled_field = has_any_filled_field or any(
                    self._is_accessibility_node_filled(n) for n in role_field_nodes
                )
                has_unfilled_visible_field = has_unfilled_visible_field or any(
                    not self._is_accessibility_node_filled(n) for n in role_field_nodes
                )

        # See _visible_body_text - excludes <script>/<style> element text
        # (e.g. a SPA's JSON hydration payload) from the keyword-matching
        # signals below (email-verification detection in particular).
        body_text = (await self._visible_body_text(page)).lower()

        return {
            "url": url,
            "headings": headings,
            "buttons": buttons,
            "has_password": has_password,
            "has_confirm_password": has_confirm_password,
            "has_file_input": has_file_input,
            "resume_already_attached": resume_already_attached,
            "has_any_filled_field": has_any_filled_field,
            "has_unfilled_visible_field": has_unfilled_visible_field,
            "visible_field_count": len(visible_fields) or role_field_count,
            "non_file_field_count": len(non_file_fields) or role_field_count,
            "apply_link_is_cross_page": apply_link_is_cross_page,
            "unchecked_required_checkbox": unchecked_required_checkbox,
            "body_text": body_text,
        }

    def _score_landing(self, s: dict) -> float:
        score = 0.0
        # Substring match, not exact - a real "Apply" CTA is rarely just the
        # bare word (e.g. Ashby's "Apply for this job"). Every other button
        # check in this adapter already matches this way (including the
        # handler that actually clicks it, _find_button_by_words); this one
        # was the odd one out, which meant a page could score too low here
        # to ever reach the click that would have revealed the real form.
        if any(w in b for b in s["buttons"] for w in _APPLY_BUTTON_WORDS):
            score += 0.6
        if s["visible_field_count"] == 0 and not s["has_password"]:
            score += 0.3
        # An "Apply" CTA sitting above an already-rendered form (confirmed
        # live on a real Greenhouse posting, whose template puts the whole
        # application form on the same page as the job description - Apply
        # just scrolls to it, it isn't a real state transition) doesn't make
        # this a landing page anymore, regardless of the CTA still being
        # present in the DOM. Only applies when the Apply CTA is NOT a
        # genuine navigation to a different page - confirmed live on a real
        # Duke University (SuccessFactors) posting, an ordinary job-
        # description landing page can have a handful of unrelated
        # incidental fields (a site-wide search box, a job-alert-
        # subscription widget) that have nothing to do with the
        # application, while its real Apply link points to a genuinely
        # different URL. Penalizing landing status there was wrong - those
        # fields aren't evidence of an already-rendered application form
        # the way they are on Greenhouse's true same-page case.
        if s["non_file_field_count"] >= 2 and not s["apply_link_is_cross_page"]:
            score -= 0.4
        return max(0.0, min(score, 1.0))

    def _score_apply(self, s: dict) -> float:
        score = 0.0
        has_login_btn = any(w in b for b in s["buttons"] for w in _LOGIN_WORDS)
        has_signup_btn = any(w in b for b in s["buttons"] for w in ("create account", "sign up", "register"))
        if has_login_btn and has_signup_btn:
            score += 0.7
        if "apply" in s["url"]:
            score += 0.2
        return min(score, 1.0)

    def _score_login(self, s: dict) -> float:
        score = 0.0
        if s["has_password"] and not s["has_confirm_password"]:
            score += 0.5
        if any(w in s["url"] for w in ("login", "signin", "sign-in")):
            score += 0.2
        if any(w in h for h in s["headings"] for w in ("log in", "login", "sign in")):
            score += 0.2
        if any(w in b for b in s["buttons"] for w in _LOGIN_WORDS):
            score += 0.1
        return min(score, 1.0)

    def _score_create_account(self, s: dict) -> float:
        score = 0.0
        if s["has_password"] and s["has_confirm_password"]:
            score += 0.5
        if any(w in s["url"] for w in ("signup", "sign-up", "register", "create-account", "create_account")):
            score += 0.2
        if any(w in h for h in s["headings"] for w in ("create account", "sign up", "register")):
            score += 0.3
        return min(score, 1.0)

    def _score_email_verification(self, s: dict) -> float:
        score = 0.0
        if any(w in s["url"] for w in ("verify", "verification")):
            score += 0.3
        if any(w in s["body_text"] for w in ("check your email", "verify your email", "verification link", "confirm your email")):
            score += 0.6
        return min(score, 1.0)

    def _score_profile_setup(self, s: dict) -> float:
        score = 0.0
        if any(w in s["url"] for w in ("profile-setup", "profile_setup", "onboarding")):
            score += 0.4
        if any(w in h for h in s["headings"] for w in ("profile", "set up your")):
            score += 0.3
        if not s["has_password"] and not s["has_file_input"] and s["visible_field_count"] > 0:
            score += 0.2
        return min(score, 1.0)

    def _score_resume_upload(self, s: dict) -> float:
        if s["resume_already_attached"]:
            # Re-scoring this as resume_upload once a file is already
            # attached would just re-trigger the same upload forever,
            # never advancing to the rest of the form's fields.
            return 0.0
        score = 0.0
        # Gated on few/no other fields, not just has_file_input alone - a
        # real single-page form (e.g. Greenhouse) has a file input on the
        # same page as every text field from the first load, and that's a
        # normal fields-to-fill APPLICATION page, not a dedicated
        # resume-upload step.
        if s["has_file_input"] and s["non_file_field_count"] < 2:
            score += 0.5
        if any(w in s["url"] for w in ("resume", "cv-upload", "upload")):
            score += 0.2
        if any(w in h for h in s["headings"] for w in ("resume", "upload your resume", "cv")):
            score += 0.3
        return min(score, 1.0)

    def _score_resume_parse_wait(self, s: dict) -> float:
        if s["has_file_input"]:
            # A genuine "parsing in progress" state follows a completed
            # upload - the file input is gone/replaced by then. If it's
            # still visibly present and empty, any "parsing"/"please wait"
            # text on the page is static instructional copy describing the
            # upload widget, not a live status. Found live against a real
            # Ashby posting: its "autofill from resume" widget permanently
            # reads "Parsing your resume. Autofilling key fields..." as
            # placeholder copy before any file has ever been selected -
            # this locked detect_state onto resume_parse_wait for the
            # entire run, on a fully-rendered 11-field form that had never
            # been touched.
            return 0.0
        score = 0.0
        if any(w in s["body_text"] for w in ("parsing", "processing your resume", "please wait")):
            score += 0.6
        if any(w in s["url"] for w in ("parsing", "processing")):
            score += 0.2
        return min(score, 1.0)

    def _score_application(self, s: dict) -> float:
        score = 0.0
        # Gated on non_file_field_count, not visible_field_count + a
        # has_file_input/resume_already_attached carve-out - the old gate
        # required a resume to already be attached before this could ever
        # score as APPLICATION, which is a chicken-and-egg deadlock for any
        # real single-page form (confirmed live on Greenhouse) where the
        # file input renders on the same page as every other field from the
        # start: nothing would ever trigger the fill logic that was
        # supposed to attach that resume in the first place. Whether a file
        # input is present or already filled no longer matters here - what
        # matters is whether there are real, substantive fields to fill.
        #
        # KNOWN GAP, NOT fixed here (two rounds tried and reverted - see
        # git history): a real Jobvite posting (NinjaOne) has a legitimate
        # single-required-field "Data Consent" page that a >= 2 gate can't
        # recognize as APPLICATION at all, falling to UNKNOWN and retrying
        # _handle_landing with a misleading "No Apply button found".
        # Loosening the gate to allow a single field when it's `required`
        # was tried next and reverted just as fast: a real Duke University
        # (SuccessFactors) posting has an ordinary job-description LANDING
        # page with an unrelated "Create Alert" job-alert-subscription
        # widget whose frequency input is ALSO genuinely marked `required`
        # in the real HTML (an opt-in widget's own internal validation, not
        # a signal about the actual application flow) - indistinguishable
        # from Jobvite's case using only generic required-attribute
        # presence. A real fix needs to know which fields belong to "the
        # form that matters" versus incidental page furniture (search
        # boxes, alert signups) - not reliably answerable from DOM
        # signals (required-ness, field count) alone. Left at the safe
        # >= 2 default; Jobvite's specific case still resolves via the
        # existing no-progress stall detector rather than silently
        # misclassifying an unrelated page as APPLICATION.
        if s["non_file_field_count"] >= 2 and not s["has_password"]:
            score += 0.4
        if any(w in s["url"] for w in ("application", "apply-form", "apply")):
            score += 0.1
        if any(w in b for b in s["buttons"] for w in _NEXT_BUTTON_WORDS):
            score += 0.3
        # A genuine "Submit Application"/"Submit your application" button
        # sitting alongside real, still-*unfilled* fields is a strong,
        # specific signal this is the actual form to fill (as opposed to a
        # bare "Apply" scroll-to-form CTA, deliberately not matched here -
        # see _score_landing). Needed because 0.4 alone sits below
        # detect_state's 0.5 confidence floor and would be classified
        # UNKNOWN despite correctly being the single highest score -
        # confirmed live on the same real Greenhouse form used to find the
        # non_file_field_count bug above, whose single-page form has no
        # "Next"/"Continue" button at all, only "Submit Application". Gated
        # on has_unfilled_visible_field so this can't fire once the form is
        # actually done, which would just re-fight _score_submit_ready for
        # the same page (two fixture regressions caught this the first time
        # this check had no such gate: a fully-filled form and a
        # already-filled-then-checked-consent form both misclassified back
        # to APPLICATION instead of staying SUBMIT_READY).
        # Uses _SUBMIT_BUTTON_WORDS, not a hardcoded "submit" substring -
        # confirmed live against the same real Recruitee posting that
        # motivated _SUBMIT_BUTTON_WORDS' "senden" addition: this check
        # used to hardcode "submit" independently of that constant, so
        # adding "senden" there alone didn't fix this bonus at all - the
        # score stayed at exactly 0.4 even after that fix deployed.
        if s["has_unfilled_visible_field"] and any(w in b for b in s["buttons"] for w in _SUBMIT_BUTTON_WORDS):
            score += 0.2
        return min(score, 1.0)

    def _score_review(self, s: dict) -> float:
        score = 0.0
        if s["unchecked_required_checkbox"]:
            score += 0.4
        if any(w in h for h in s["headings"] for w in ("review", "confirm your")):
            score += 0.3
        # Same substring-vs-exact-membership bug as _score_landing: `w in
        # s["buttons"]` checks whether "submit" is itself a whole element of
        # the list, not a substring of one - a button reading "Submit Now"
        # or "Submit Your Application" would never match.
        if any(w in b for b in s["buttons"] for w in ("submit", "submit application")) and s["unchecked_required_checkbox"]:
            score += 0.2
        return min(score, 1.0)

    def _score_submit_ready(self, s: dict) -> float:
        if s["unchecked_required_checkbox"]:
            return 0.0
        if s["visible_field_count"] == 0:
            # A genuine review/submit-ready page always carries some visible
            # form state (filled fields, a consent checkbox, a read-only
            # summary input) - zero visible fields means either a plain
            # landing/description page whose CTA happens to contain a
            # submit-ish word ("Apply for this job"), or a client-rendered
            # SPA that fired networkidle before it actually painted the
            # form. Found live against a real Ashby posting: the page still
            # read "you need to enable javascript to run this app" when
            # detect_state scored it submit_ready at 0.5 confidence purely
            # from the word "apply" in a nav CTA - nothing had been filled.
            # Misclassifying either case as submit-ready is the single most
            # dangerous mistake this state machine can make, so both must
            # score 0 here rather than fall through to the button/heading
            # heuristics below.
            return 0.0
        if not s["has_any_filled_field"]:
            # Fields existing isn't fields being filled - a single-page
            # form's real "Submit Application" button is visible from the
            # moment the page renders, long before anything's been typed,
            # and a resume being attached doesn't mean the rest of the
            # form's required fields (name, email, custom questions) are.
            return 0.0
        if s["has_unfilled_visible_field"]:
            # There's still a real, empty, fillable field visible - not
            # remotely ready to submit yet, no matter how confidently the
            # buttons/headings below would otherwise score it. Without
            # this, a partially-filled single-page form ties APPLICATION
            # against SUBMIT_READY every loop (APPLICATION wins the tie,
            # the safe side, but nothing changes between iterations once
            # every resolvable field keeps resolving to the same value) -
            # the run just re-fills the same data forever until
            # MAX_TRANSITIONS gives up, confirmed live against a real
            # Ashby posting. Scoring 0 here instead of tying lets
            # APPLICATION win outright while work remains, and only
            # SUBMIT_READY once it's actually, verifiably done.
            return 0.0
        score = 0.0
        if any(w in b for b in s["buttons"] for w in _SUBMIT_BUTTON_WORDS):
            score += 0.5
        if any(w in h for h in s["headings"] for w in ("review", "confirm")):
            score += 0.2
        return min(score, 1.0)

    async def detect_state(self, page: Page) -> Tuple[BrowserState, float]:
        confirmation = await self.detect_confirmation(page)
        if confirmation.confirmed:
            return BrowserState.SUBMITTED, confirmation.confidence

        signals = await self._gather_signals(page)
        scores = {
            BrowserState.LANDING: self._score_landing(signals),
            BrowserState.APPLY: self._score_apply(signals),
            BrowserState.LOGIN: self._score_login(signals),
            BrowserState.CREATE_ACCOUNT: self._score_create_account(signals),
            BrowserState.EMAIL_VERIFICATION: self._score_email_verification(signals),
            BrowserState.PROFILE_SETUP: self._score_profile_setup(signals),
            BrowserState.RESUME_UPLOAD: self._score_resume_upload(signals),
            BrowserState.RESUME_PARSE_WAIT: self._score_resume_parse_wait(signals),
            BrowserState.APPLICATION: self._score_application(signals),
            BrowserState.REVIEW: self._score_review(signals),
            BrowserState.SUBMIT_READY: self._score_submit_ready(signals),
        }
        best_state, best_score = max(scores.items(), key=lambda kv: kv[1])
        self._last_detection_reasoning = {
            "signals": signals,
            "scores": {state.value: score for state, score in scores.items()},
        }
        if best_score < 0.5:
            return BrowserState.UNKNOWN, best_score
        return best_state, best_score

    def get_last_detection_reasoning(self) -> dict:
        return self._last_detection_reasoning

    async def handle_state(self, state: BrowserState, page: Page, ctx: RunContext) -> StateHandlerResult:
        handlers = {
            BrowserState.LANDING: self._handle_landing,
            BrowserState.APPLY: self._handle_apply,
            BrowserState.LOGIN: self._handle_login,
            BrowserState.CREATE_ACCOUNT: self._handle_create_account,
            BrowserState.PROFILE_SETUP: self._handle_profile_setup,
            BrowserState.RESUME_UPLOAD: self._handle_resume_upload,
            BrowserState.RESUME_PARSE_WAIT: self._handle_resume_parse_wait,
            BrowserState.APPLICATION: self._handle_application_page,
            BrowserState.REVIEW: self._handle_review,
        }
        handler = handlers.get(state)
        if handler is None:
            return StateHandlerResult(success=False, error=f"No generic handler for state {state.value}")
        return await handler(page, ctx)

    async def _handle_landing(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        """Click Apply and verify it actually did something - found live
        against a real Workday posting where clicking a real, visible Apply
        link (valid href, no JS errors) left the page completely unchanged
        even after several seconds, and detect_state kept re-classifying the
        same unchanged page as LANDING on every subsequent loop iteration.
        Without this check that burns the entire MAX_TRANSITIONS/wall-clock
        budget (40 identical checkpoints) before finally giving up with a
        vague "exceeded transition/time budget" error - failing fast here
        instead gives a specific, actionable one."""
        btn = await self._find_button_by_words(page, _APPLY_BUTTON_WORDS)
        if not btn:
            return StateHandlerResult(success=False, error="No Apply button found")

        before_url = page.url
        before_text = await page.text_content("body")

        await btn.click()
        await page.wait_for_timeout(2000)

        if page.url == before_url and await page.text_content("body") == before_text:
            return StateHandlerResult(
                success=False,
                error="Clicked Apply but the page did not change (no navigation, no content change)",
            )
        return StateHandlerResult(success=True)

    async def _ensure_credential(self, ctx: RunContext) -> Optional[StateHandlerResult]:
        """Fetch/create the vault credential if it isn't already set.

        Normally happens once, in _handle_apply. But a real ATS can skip
        straight from some earlier state (resume upload, in this case)
        directly to a login/register FORM with no distinct "apply" landing
        step in between to have run _handle_apply at all - confirmed live
        against Epic's real Avature-hosted careers portal, which goes
        resume-upload -> register form directly. Without this, _handle_login/
        _handle_create_account had no credential to fill and could only
        fail with "No credential available" on every such site, forever.

        Returns an error result if the fetch failed or the credential isn't
        usable; None if ctx.credential is now populated (whether it already
        was, or was freshly fetched here).
        """
        if ctx.credential:
            return None
        try:
            ctx.credential = await get_or_create_credential(
                user_id=ctx.user_id,
                ats_platform=ctx.ats_platform,
                tenant_key=ctx.tenant_key,
                email=ctx.application_data.email,
            )
        except Exception as exc:
            return StateHandlerResult(success=False, error=f"Credential vault lookup failed: {exc}")

        if ctx.credential["status"] != "active":
            return StateHandlerResult(
                success=False,
                error=f"Existing credential for this tenant is in state '{ctx.credential['status']}' - not safe to retry automatically",
            )
        return None

    async def _handle_apply(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        error = await self._ensure_credential(ctx)
        if error:
            return error

        words = ("create account", "sign up", "register") if ctx.credential["created"] else _LOGIN_WORDS
        btn = await self._find_button_by_words(page, words)
        if not btn:
            return StateHandlerResult(success=False, error="Could not find login/signup entry point")
        await btn.click()
        return StateHandlerResult(success=True)

    async def _fill_credential_form(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        error = await self._ensure_credential(ctx)
        if error:
            return error

        form = await self.inspect_form(page)
        password_fields = [f for f in form.fields if f.input_type == "password"]
        confirm_field = next(
            (
                f for f in password_fields
                if any(kw in f.name.lower() or kw in (f.label or "").lower() for kw in _CONFIRM_PASSWORD_KEYWORDS)
            ),
            None,
        )
        primary_password_field = next((f for f in password_fields if f is not confirm_field), None)
        email_field = next((f for f in form.fields if f.input_type == "email" or "email" in f.name.lower()), None)

        if email_field:
            await self.fill_field(page, email_field, ctx.credential["email"])
        if primary_password_field:
            await self.fill_field(page, primary_password_field, ctx.credential["password"])
        if confirm_field:
            await self.fill_field(page, confirm_field, ctx.credential["password"])

        # Some real sites (confirmed live: Epic's real Avature-hosted
        # careers portal, a 17-field "Employment Inquiry" page combining
        # account credentials with other application-specific questions on
        # the SAME page) put real, required, non-credential fields on a
        # LOGIN/CREATE_ACCOUNT-classified page - fill those the same way
        # _handle_application_page does, or the site's own validation
        # rejects the submit and the page just re-renders itself forever.
        credential_field_names = {f.name for f in (email_field, primary_password_field, confirm_field) if f}
        other_fields = [f for f in form.fields if f.name not in credential_field_names and f.input_type not in ("password", "file")]
        if other_fields:
            app_data_dict = ctx.application_data.model_dump()
            form_fingerprint = compute_form_fingerprint([f.name for f in form.fields])
            for field in other_fields:
                value = await resolve_field_value(field, ctx, app_data_dict, form_fingerprint)
                if ctx.pending_question:
                    return StateHandlerResult(success=True)
                if value is None:
                    continue
                result = await self.fill_field(page, field, str(value))
                if result.success:
                    ctx.filled_fields[field.name] = value

        # Scoped to the actual form being filled, not the whole page - a
        # word list like ("log in", "sign in") is likely to also match an
        # unrelated persistent header/nav link that just happens to appear
        # earlier in DOM order than the form's own submit control (found
        # live: Epic's real Avature-hosted careers portal has exactly this
        # - a page-header "Log in" link above a combined "sign in or
        # register" form). Intent-aware for the same reason _handle_apply
        # already is: a freshly vault-created credential means this is a
        # brand-new account that needs to REGISTER, not sign in - a
        # combined sign-in/register page offers both, and clicking the
        # wrong one for a brand-new account fails validation (no such
        # account exists yet) and just re-renders the same page forever.
        form_element = await self._find_visible_form(page)
        opposite_intent_words = _LOGIN_WORDS if ctx.credential["created"] else ("create account", "sign up", "register")
        preferred_words = ("create account", "sign up", "register") if ctx.credential["created"] else _LOGIN_WORDS
        submit_btn = await self._find_button_by_words(page, preferred_words, scope=form_element)
        if not submit_btn:
            submit_btn = await self._find_button_by_words(page, _SUBMIT_BUTTON_WORDS, scope=form_element)
        if not submit_btn:
            # Some real sites (confirmed live: Epic's real Avature-hosted
            # careers portal) use ONE unified button for both login and
            # registration - the site itself decides which based on
            # whether the email is already known, so there's no
            # dedicated register-worded control to prefer. Falling back to
            # the opposite intent's wording rather than giving up outright
            # - still tried last, after every chance to find the
            # genuinely correct one first.
            submit_btn = await self._find_button_by_words(page, opposite_intent_words, scope=form_element)
        if not submit_btn:
            # Some real sites (confirmed live: Epic's real Avature-hosted
            # careers portal) combine account credentials with other
            # application-specific fields on the SAME page, advanced by a
            # completely generic "Next" control rather than anything
            # login/register-worded at all - the same control every other
            # multi-page handler in this file already falls back to.
            submit_btn = await self._find_button_by_words(page, _NEXT_BUTTON_WORDS, scope=form_element)
        if not submit_btn:
            # Confirmed live against a real Taleo posting (Costco): the
            # page's "next" control is a plain <a> SIBLING of the <form>
            # element, not a descendant of it - every attempt above,
            # scoped to form_element, necessarily finds nothing regardless
            # of wording. Unlike the login/signup-worded tiers above (whose
            # scoping exists specifically to avoid matching an unrelated
            # header "Log in" nav link - see the comment at form_element's
            # definition), an unscoped page-wide search for
            # _NEXT_BUTTON_WORDS carries much lower collision risk: "next"/
            # "continue"/"proceed" aren't persistent-header vocabulary the
            # way "log in"/"sign in" are. Tried last, only once every
            # scoped attempt (including the scoped _NEXT_BUTTON_WORDS
            # attempt just above) has already failed.
            submit_btn = await self._find_button_by_words(page, _NEXT_BUTTON_WORDS)
        if not submit_btn:
            return StateHandlerResult(success=False, error="No submit control found on credential form")
        await submit_btn.click()
        await page.wait_for_timeout(300)
        return StateHandlerResult(success=True)

    async def _handle_login(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        return await self._fill_credential_form(page, ctx)

    async def _handle_create_account(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        return await self._fill_credential_form(page, ctx)

    async def _handle_profile_setup(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        form = await self.inspect_form(page)
        app_data_dict = ctx.application_data.model_dump()
        for field in form.fields:
            if field.input_type == "file":
                continue
            value = ctx.field_mapper.get_value_for_field(field, app_data_dict)
            if value is None and field.input_type == "select" and field.options:
                value = field.options[0]
            if value is None:
                continue
            await self.fill_field(page, field, str(value))

        submit_btn = await self._find_button_by_words(page, _SUBMIT_BUTTON_WORDS + _NEXT_BUTTON_WORDS)
        if submit_btn:
            await submit_btn.click()
            return StateHandlerResult(success=True)
        return StateHandlerResult(success=False, error="No continue control found on profile setup form")

    async def _handle_resume_upload(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        if not ctx.application_data.resume_path:
            return StateHandlerResult(success=False, error="No resume_path available to upload")

        form = await self.inspect_form(page)
        file_field = next((f for f in form.fields if f.input_type == "file"), None)
        if file_field is None:
            return StateHandlerResult(success=False, error="No file input found for resume upload")

        result = await self.upload_document(page, file_field, ctx.application_data.resume_path)
        if not result.success:
            return StateHandlerResult(success=False, error=result.error)

        # Only advance via an explicit next/continue control, never a
        # submit-worded one. A dedicated resume-upload STEP (its own page,
        # like the mock fixture) has a real "Upload & Continue" button; a
        # single-page form where the resume is just one of many fields does
        # not, and the only button a broader search would find is the
        # form's actual final submit control - clicking that here would
        # submit an application missing every other field, bypassing the
        # submit_ready/awaiting_approval gate entirely (found live against
        # a real Ashby posting). If there's no next/continue control, this
        # is that single-page case: leave it for detect_state to
        # re-classify and hand off to the normal field-filling path.
        next_btn = await self._find_button_by_words(page, _NEXT_BUTTON_WORDS)
        if next_btn:
            await next_btn.click()
        return StateHandlerResult(success=True)

    async def _handle_resume_parse_wait(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        return StateHandlerResult(success=True)

    async def _handle_application_page(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        form = await self.inspect_form(page)
        app_data_dict = ctx.application_data.model_dump()
        form_fingerprint = compute_form_fingerprint([f.name for f in form.fields])

        for field in form.fields:
            if field.input_type == "file":
                # File fields used to be skipped entirely here on the
                # assumption a resume is always uploaded by a dedicated
                # RESUME_UPLOAD state first - true for a mock-fixture-style
                # multi-step flow, but not for a real single-page form
                # (confirmed live on Greenhouse) where the resume's file
                # input renders alongside every other field on the same
                # page detect_state now correctly classifies as APPLICATION.
                # Without this, the resume (a required field) never gets
                # filled, has_unfilled_visible_field never clears, and the
                # run just re-fills the same already-filled text fields
                # forever. Only the field that canonically maps to "resume"
                # is targeted - a separate cover-letter file upload field on
                # the same form is deliberately left alone, since there is
                # no cover-letter *file* to put there (only generated text).
                if (
                    ctx.field_mapper.map_to_canonical(field) == "resume"
                    and ctx.application_data.resume_path
                ):
                    upload_result = await self.upload_document(page, field, ctx.application_data.resume_path)
                    if upload_result.success:
                        ctx.filled_fields[field.name] = ctx.application_data.resume_path
                continue
            value = await resolve_field_value(field, ctx, app_data_dict, form_fingerprint)
            if ctx.pending_question:
                return StateHandlerResult(success=True)
            if value is None:
                continue
            result = await self.fill_field(page, field, str(value))
            if result.success:
                ctx.filled_fields[field.name] = value

        # Only attempt to navigate if there's actually a next/continue
        # control to click - a single-page form (confirmed live against a
        # real Ashby posting: every field on one page, no step-by-step
        # flow) has nothing to advance to, only its final submit control.
        # Fields are filled either way; let detect_state re-classify
        # (likely SUBMIT_READY) rather than treating "nothing to click"
        # as a failure.
        next_btn = await self._find_button_by_words(page, _ADVANCE_BUTTON_WORDS)
        if next_btn is None:
            return StateHandlerResult(success=True)

        nav_result = await self.navigate_next(page)
        if not nav_result.success:
            return StateHandlerResult(success=False, error=f"Failed to advance past application page: {nav_result.error}")
        return StateHandlerResult(success=True)

    async def _handle_review(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        form = await self.inspect_form(page)
        app_data_dict = ctx.application_data.model_dump()
        form_fingerprint = compute_form_fingerprint([f.name for f in form.fields])

        for field in form.fields:
            if field.input_type == "checkbox":
                result = await self.fill_field(page, field, "true")
                if result.success:
                    ctx.filled_fields[field.name] = True
                continue
            value = await resolve_field_value(field, ctx, app_data_dict, form_fingerprint)
            if ctx.pending_question:
                return StateHandlerResult(success=True)
            if value is None:
                continue
            result = await self.fill_field(page, field, str(value))
            if result.success:
                ctx.filled_fields[field.name] = value

        return StateHandlerResult(success=True)
