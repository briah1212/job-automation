"""Regression test: BrowserWorker._navigate must tolerate a "networkidle"
wait timing out, since the navigation itself has still very likely
completed - only genuine navigation failures (DNS errors, connection
refused, etc.) should propagate.

Found live against a real application: Epic's real Avature-hosted careers
portal (reached via a real LinkedIn job posting during production
validation) has persistent background network activity that means
"networkidle" never fires within 30s, even though the page loads and is
fully usable. Before this fix, that timeout was completely unhandled and
crashed the whole task to a hard failed status before the state machine
ever got a chance to run.
"""
from unittest.mock import AsyncMock

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from browser_worker.worker import BrowserWorker


class _FakePage:
    def __init__(self, goto_side_effect):
        self.goto = AsyncMock(side_effect=goto_side_effect)


@pytest.mark.asyncio
async def test_navigate_swallows_networkidle_timeout():
    page = _FakePage(PlaywrightTimeoutError("Timeout 30000ms exceeded"))
    worker = BrowserWorker(headless=True)

    # Must not raise.
    await worker._navigate(page, "https://epic.avature.net/Careers/RegisterMethod?folderId=740")
    page.goto.assert_awaited_once()


@pytest.mark.asyncio
async def test_navigate_reraises_genuine_navigation_failure():
    page = _FakePage(RuntimeError("net::ERR_NAME_NOT_RESOLVED"))
    worker = BrowserWorker(headless=True)

    with pytest.raises(RuntimeError):
        await worker._navigate(page, "https://this-domain-does-not-exist.invalid")
