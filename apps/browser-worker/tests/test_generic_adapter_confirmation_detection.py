"""Regression test: detect_confirmation must not false-positive on generic
words ("thank you", "confirmation") appearing in ordinary, unrelated
visible text - it must require a specific, multi-word confirmation phrase.

CRITICAL finding, confirmed live against a real Jobvite posting (NinjaOne):
the old implementation accumulated partial confidence per generic keyword
match (0.3 each, "thank you" and "confirmation" among them) with a 0.5
threshold, so ANY TWO such words appearing anywhere in the page's visible
text reported a full submission. A real NinjaOne candidate consent page's
privacy-policy legal text plainly contains both ("Thank you for
considering a job opportunity..." and "...you may have received a
confirmation email...") despite neither "I Accept" nor "I Decline" having
been clicked, and no application field ever having been filled - the
single most dangerous kind of bug this system can have, a false-positive
"success" report.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.adapters.generic_adapter import GenericAdapter

# Excerpted from the actual real page text this bug was found on - not
# fabricated, this really is what a legal privacy-policy disclaimer says.
_REAL_JOBVITE_PRIVACY_POLICY_TEXT = """
Data Consent
Location of Residence and Language:
NINJAONE APPLICANT AND CANDIDATE PRIVACY POLICY
Thank you for considering a job opportunity at NinjaOne!
This Applicant and Candidate Privacy Policy applies to the processing of
personal data collected in connection with career opportunities.
Please note that if you were referred to the application process by
someone else, you may have received a confirmation email when your
referral was submitted.
I Accept
I Decline
"""

_REAL_CONFIRMATION_PAGE_TEXT = """
Thank you for applying to Senior Software Engineer at Example Corp!
Your application has been received and our team will review it shortly.
"""


async def _confirmation_for(body_text: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(f"<body><pre>{body_text}</pre></body>")
        result = await GenericAdapter().detect_confirmation(page)
        await browser.close()
        return result


class TestNoFalsePositiveOnUnrelatedText:
    @pytest.mark.asyncio
    async def test_privacy_policy_text_is_not_a_confirmation(self):
        result = await _confirmation_for(_REAL_JOBVITE_PRIVACY_POLICY_TEXT)
        assert result.confirmed is False

    @pytest.mark.asyncio
    async def test_bare_thank_you_alone_is_not_a_confirmation(self):
        result = await _confirmation_for("Thank you for your interest in our company.")
        assert result.confirmed is False

    @pytest.mark.asyncio
    async def test_bare_confirmation_word_alone_is_not_a_confirmation(self):
        result = await _confirmation_for("Please check your email for a confirmation link to verify your account.")
        assert result.confirmed is False


class TestRealConfirmationStillDetected:
    @pytest.mark.asyncio
    async def test_genuine_confirmation_phrase_is_detected(self):
        result = await _confirmation_for(_REAL_CONFIRMATION_PAGE_TEXT)
        assert result.confirmed is True

    @pytest.mark.asyncio
    async def test_application_submitted_successfully_is_detected(self):
        result = await _confirmation_for("Your application submitted successfully. We'll be in touch soon.")
        assert result.confirmed is True
