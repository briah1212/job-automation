"""Dismiss cookie/consent banners that block the page underneath them.

Live research against Lever found a cookie consent banner ("Deny"/"Accept")
rendered on top of the job posting before the Apply control is reachable -
a near-universal pattern across commercial ATS platforms, not specific to
one vendor, so this lives in the generic layer rather than any adapter.

Prefers the most privacy-preserving choice available (reject/decline non-
essential cookies), falling back to accept only when no reject option is
offered, since some banners require a choice before the page becomes
interactive at all.
"""
import logging

from playwright.async_api import Page

logger = logging.getLogger(__name__)

_REJECT_WORDS = ("reject all", "reject", "decline", "deny", "necessary only", "essential only")
_ACCEPT_WORDS = ("accept all", "accept cookies", "i agree", "allow all", "got it")


async def _find_consent_button(page: Page, words: tuple) -> object:
    candidates = await page.query_selector_all("button:visible, a[role='button']:visible")
    for el in candidates:
        text = ((await el.text_content()) or "").strip().lower()
        if text and any(word in text for word in words):
            return el
    return None


async def dismiss_cookie_consent(page: Page) -> bool:
    """Click the most privacy-preserving option on a visible consent banner.

    Returns True if a banner was found and dismissed, False if none was
    present. Intended to be called once, immediately after the initial
    navigation - the word lists (especially bare "deny"/"reject") are broad
    enough that running this on every state-machine tick risks misfiring on
    an unrelated button later in the flow (e.g. a "Reject changes" control
    on a later form page).
    """
    try:
        btn = await _find_consent_button(page, _REJECT_WORDS)
        choice = "reject"
        if btn is None:
            btn = await _find_consent_button(page, _ACCEPT_WORDS)
            choice = "accept"
        if btn is None:
            return False
        await btn.click()
        logger.info(f"Dismissed cookie consent banner ({choice})")
        await page.wait_for_timeout(200)
        return True
    except Exception as exc:
        logger.debug(f"Cookie consent dismissal failed (non-fatal): {exc}")
        return False
