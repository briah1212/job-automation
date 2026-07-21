"""Detect a live, interactive CAPTCHA challenge on the page.

Spec-mandated: no CAPTCHA or anti-bot circumvention of any kind. This module
never attempts to solve or interact with a challenge - it only recognizes
one is present so the caller can pause for a human (PauseReason.CAPTCHA).

Live research turned up two vendors in real ATS flows: reCAPTCHA (Greenhouse,
Ashby) and hCaptcha (Lever). Both are handled generically here rather than
as adapter-specific checks, since the widget markup is standardized by the
vendor, not the ATS.

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
"""
import logging

from playwright.async_api import Page

logger = logging.getLogger(__name__)

_CAPTCHA_CHALLENGE_SELECTORS = (
    "div.g-recaptcha[data-sitekey]:visible",
    "div.h-captcha[data-sitekey]:visible",
    "div.cf-turnstile[data-sitekey]:visible",
    "iframe[title='reCAPTCHA']:visible",
    "iframe[title*='hCaptcha' i]:visible",
    "iframe[src*='hcaptcha.com']:visible",
    "iframe[src*='challenges.cloudflare.com']:visible",
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
