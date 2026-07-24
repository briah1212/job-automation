"""Detect a live, interactive CAPTCHA challenge on the page.

Spec-mandated: no CAPTCHA or anti-bot circumvention of any kind. This module
never attempts to solve or interact with a challenge - it only recognizes
one is present so the caller can pause for a human (PauseReason.CAPTCHA).

Live research turned up three vendors in real ATS flows: reCAPTCHA
(Greenhouse, Ashby), hCaptcha (Lever), and DataDome (SmartRecruiters -
confirmed live against a real WesternDigital posting's "OneClick" apply
flow, whose entire page body was replaced by DataDome's block/challenge
shell - `x-datadome: protected` response header, a script pulled from
captcha-delivery.com, and a `#cmsg` "Please enable JS and disable any ad
blocker" placeholder in place of any real content). All three are handled
generically here rather than as adapter-specific checks, since the widget
markup is standardized by the vendor, not the ATS.

Deliberately NOT triggered by mere presence of a `g-recaptcha-response` /
`h-captcha-response` hidden field - that field is injected on the page
whenever the vendor's script loads at all, including "invisible" reCAPTCHA
v3, which scores traffic silently in the background and never presents a
challenge to the user. Triggering manual intervention on every page with a
v3 badge would make the pause fire on nearly every Greenhouse/Ashby
application regardless of whether a human was ever needed. Instead this
checks for the actual interactive widget container/iframe, which the
vendor only renders when an explicit (usually v2-style) checkbox or
challenge is being presented.

That "invisible v3 badge" exclusion was stated as design intent here but
not actually implemented correctly for reCAPTCHA specifically - confirmed
live against a real Jobvite posting (NinjaOne): its candidate application
form legitimately embeds an invisible v3 badge (`iframe[title='reCAPTCHA']`,
256x60, `src` containing `size=invisible`) that scores traffic silently
and never presents a challenge, exactly the case this module says it
shouldn't trigger on - but the old selector, `iframe[title='reCAPTCHA']:
visible` alone, matched it anyway (a 256x60 iframe IS Playwright-:visible
- "invisible" in reCAPTCHA's own vocabulary means "doesn't ever present an
interactive challenge to the user," not "has zero size/CSS visibility").
The genuine, confirmed-live interactive v2 checkbox (a real BambooHR
posting) has the same `title='reCAPTCHA'` but a distinctly different
size (304x78, not 256x60) and `size=normal` (not `size=invisible`) in its
own iframe `src`, which is what the selector below now actually checks.
"""
import logging

from playwright.async_api import Page

logger = logging.getLogger(__name__)

_CAPTCHA_CHALLENGE_SELECTORS = (
    "div.g-recaptcha[data-sitekey]:visible",
    "div.h-captcha[data-sitekey]:visible",
    "div.cf-turnstile[data-sitekey]:visible",
    "iframe[title='reCAPTCHA']:visible:not([src*='size=invisible'])",
    "iframe[title*='hCaptcha' i]:visible",
    "iframe[src*='hcaptcha.com']:visible",
    "iframe[src*='challenges.cloudflare.com']:visible",
    # DataDome's block/challenge shell entirely replaces the real page
    # (not a widget floating within one), so unlike the others above this
    # isn't gated on :visible - #cmsg is specific enough to DataDome's own
    # template that presence alone, regardless of momentary visibility, is
    # a reliable signal without also matching an unrelated real page.
    "#cmsg",
    "script[src*='captcha-delivery.com']",
)


async def detect_captcha_challenge(page: Page) -> bool:
    """True if an interactive CAPTCHA widget is currently visible on the page."""
    for selector in _CAPTCHA_CHALLENGE_SELECTORS:
        try:
            if await page.query_selector(selector):
                logger.info(f"CAPTCHA challenge detected via selector: {selector}")
                return True
        except Exception as exc:
            logger.debug(f"CAPTCHA selector check failed for {selector!r}: {exc}")
    return False
