"""Regression test: an unexpected exception raised by an adapter's
handle_state must degrade to the same graceful manual_intervention
escalation as a handled failure, not crash the whole task.

Found live against a real Ashby posting during production validation
(docs/browser-state-machine-design.md): inspect_form's "No visible form
found on page" ValueError, raised deep inside _handle_resume_upload,
propagated all the way out of run_state_machine and crashed the task to a
hard WorkflowStatus.failed - bypassing the state machine's entire premise
that automation never fails silently/uncontrolled, and skipping the
replay-friendly manual_intervention pause every other failure mode gets.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.services.field_mapper import FieldMapper
from browser_worker.state import BrowserState, PauseReason, RunContext
from browser_worker.worker import BrowserWorker


class _RaisingAdapter:
    """Minimal fake adapter: classifies the page as APPLICATION, then blows
    up in handle_state exactly like inspect_form did against the real
    formless Ashby page."""

    def get_name(self) -> str:
        return "Raising"

    async def detect_state(self, page):
        return BrowserState.APPLICATION, 1.0

    def get_last_detection_reasoning(self) -> dict:
        return {}

    async def handle_state(self, state, page, ctx):
        raise ValueError("No visible form found on page")

    async def detect_confirmation(self, page):
        raise AssertionError("should not be reached")


@pytest.fixture
async def pw_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content("<html><body>test</body></html>")
        yield page
        await browser.close()


@pytest.mark.asyncio
async def test_handler_exception_escalates_instead_of_propagating(pw_page):
    worker = BrowserWorker(headless=True)
    ctx = RunContext(
        session_id="test-exc",
        application_url="http://example.com",
        application_data=None,
        user_id="u1",
        field_mapper=FieldMapper(),
    )

    result = await worker.run_state_machine(pw_page, _RaisingAdapter(), ctx)

    assert result["status"] == "manual_intervention"
    assert result["pause_reason"] == PauseReason.REPEATED_FAILURE.value
    assert "No visible form found on page" in result["detail"]
