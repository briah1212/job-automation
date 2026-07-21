"""Distinguish genuinely-fillable form fields from bot-trap honeypots.

Playwright's `:visible` pseudo-class (display/visibility/opacity + non-zero
box) is necessary but not sufficient. Live research against Workday found a
field (`data-automation-id="beecatcher"`, `name="website"`) that is
`display:block; visibility:visible; opacity:1` with a 1px x 0.01px box - it
passes `:visible` cleanly while being unusable by a human. That is a
honeypot: real applicants never see or fill it, so any value written there
is a bot signal that risks the whole session getting flagged.

A blunt "reject anything under N pixels" rule is unsafe in the other
direction: real ATS platforms routinely render legitimate fields with
near-zero native geometry -

- File inputs hidden behind a styled "Upload"/"Attach" button (Ashby: 1x1)
- Custom-styled <select>/radio widgets where the native control is a
  near-invisible target under a styled overlay (Greenhouse EEO dropdowns)
- CAPTCHA response fields the vendor's own JS populates, never the applicant
  (Greenhouse/Ashby `g-recaptcha-response`, Lever `h-captcha-response`)
- Fields hidden by progressive disclosure until a prior answer reveals them
  (Lever's `eeo[disabilitySignature]`, 0x0 until "yes" is chosen)

The corroborating signal that actually separates these from a honeypot: a
honeypot exists specifically to have no human-discoverable label, because a
real applicant must never notice or fill it. Everything else in the list
above still has a label a sighted user would read (an associated <label>,
aria-label, or wrapping text) even though the native control itself is
visually suppressed in favor of custom UI.
"""
import logging
from typing import Optional

from playwright.async_api import ElementHandle

logger = logging.getLogger(__name__)

_NEAR_ZERO_PX = 2
_NON_APPLICANT_FIELD_MARKERS = ("recaptcha", "hcaptcha", "turnstile", "captcha")

_HAS_LABEL_JS = """
el => {
    if (el.getAttribute('aria-label')) return true;
    if (el.getAttribute('aria-labelledby')) return true;
    if (el.id) {
        try {
            if (document.querySelector(`label[for="${CSS.escape(el.id)}"]`)) return true;
        } catch (e) { /* invalid id for CSS.escape - fall through */ }
    }
    const wrappingLabel = el.closest('label');
    if (wrappingLabel && wrappingLabel.textContent.trim()) return true;
    return false;
}
"""


async def is_genuinely_fillable(el: ElementHandle) -> bool:
    """True if a real applicant could plausibly see and fill this field.

    Callers should apply this only to elements that already passed a
    `:visible`-style check - it is a refinement on top, not a replacement.
    """
    try:
        input_type = (await el.get_attribute("type") or "").lower()

        # File inputs are near-universally replaced by a custom "Upload"/
        # "Attach" button across every ATS studied - never a honeypot pattern.
        if input_type == "file":
            return True

        box = await el.bounding_box()
        if box is not None and (box["width"] >= _NEAR_ZERO_PX or box["height"] >= _NEAR_ZERO_PX):
            return True

        name = (await el.get_attribute("name") or "").lower()
        elem_id = (await el.get_attribute("id") or "").lower()
        combined = f"{name} {elem_id}"
        if any(marker in combined for marker in _NON_APPLICANT_FIELD_MARKERS):
            # CAPTCHA response fields are populated by vendor JS, never by
            # applicant data - correctly excluded from fill, not a honeypot.
            return False

        has_label = await el.evaluate(_HAS_LABEL_JS)
        if not has_label:
            logger.debug(
                "Excluding near-zero-size field with no discoverable label "
                "(name=%r id=%r) - treating as honeypot", name, elem_id
            )
        return bool(has_label)

    except Exception as exc:
        logger.debug(f"is_genuinely_fillable check failed, excluding field defensively: {exc}")
        return False
