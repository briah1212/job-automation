"""Lightweight internal HTTP service: render a URL with a real browser and
return its genuinely visible text.

Exists because backend/worker.py's job-extraction fetch is a plain httpx GET
with no JS engine at all, and the job-worker/api containers have no browser
dependency of any kind - confirmed live, repeatedly, this session: a modern
client-rendered SPA (Ashby's job board, a Workday-hosted posting) returns
either a near-empty shell ("You need to enable JavaScript to run this app.")
or literally zero real content to that fetch, so job extraction silently
produces nothing useful (or, worse, a plausible-looking but entirely
fabricated result once an LLM is asked to make sense of an empty/near-empty
input). browser-worker already has Playwright + Chromium installed for
application automation - this reuses that same image/dependency instead of
adding a second, duplicate browser install to the job-worker/api containers.

Runs alongside queue_worker.py's poll loop in the same container/process
(see queue_worker.py's __main__ block), not as a separate service - it needs
Playwright, which is already installed here and nowhere else.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, status
from playwright.async_api import async_playwright, Browser
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")
_NAVIGATION_TIMEOUT_MS = 20_000
# 1.5s was enough for Ashby but too short for Workday, confirmed live: a
# direct browser session against a real Workday posting only had the actual
# job description text (as opposed to just the cookie-consent banner) render
# in by ~3-4s after domcontentloaded. Workday's job-detail view loads via a
# secondary API call after the shell mounts, unlike Ashby's more immediate
# hydration.
_SETTLE_WAIT_MS = 4_000

# Same clone-and-strip approach as generic_adapter.py's _visible_body_text -
# document.body.textContent (or Playwright's page.text_content("body"))
# includes <script>/<style> element text, which for a real SPA is routinely
# a full JSON hydration payload, not anything a human would call "visible".
_VISIBLE_TEXT_JS = """() => {
    const clone = document.body.cloneNode(true);
    clone.querySelectorAll('script, style').forEach(el => el.remove());
    return clone.textContent || '';
}"""

_playwright_ctx = None
_browser: Optional[Browser] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _playwright_ctx, _browser
    _playwright_ctx = await async_playwright().start()
    # One shared browser process for the server's lifetime - launching a new
    # Chromium process per request would make every render call pay a
    # multi-second startup cost. Each request still gets its own isolated
    # BrowserContext (see /render below), so concurrent requests don't share
    # cookies/storage with each other.
    _browser = await _playwright_ctx.chromium.launch(headless=True)
    logger.info("render_server: shared Chromium browser launched")
    try:
        yield
    finally:
        await _browser.close()
        await _playwright_ctx.stop()


app = FastAPI(lifespan=lifespan)


class RenderRequest(BaseModel):
    url: str


class RenderResponse(BaseModel):
    success: bool
    text: Optional[str] = None
    error: Optional[str] = None


def _require_internal_api_key(x_internal_api_key: Optional[str] = Header(default=None)) -> None:
    """Mirrors backend/app/api/deps.py's require_internal_api_key - this
    port isn't published to the host, but the docker network is still a
    shared trust boundary with other containers, so the same gate applies."""
    if not x_internal_api_key or x_internal_api_key != _INTERNAL_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal API key")


@app.post("/render", response_model=RenderResponse)
async def render(req: RenderRequest, _: None = Depends(_require_internal_api_key)) -> RenderResponse:
    if _browser is None:
        return RenderResponse(success=False, error="browser not initialized")

    context = await _browser.new_context(
        user_agent="job-automation-worker/1.0 (+https://github.com/brianhsu/job-automation)"
    )
    try:
        page = await context.new_page()
        try:
            await page.goto(req.url, timeout=_NAVIGATION_TIMEOUT_MS, wait_until="domcontentloaded")
        except Exception as exc:
            return RenderResponse(success=False, error=f"navigation failed: {exc}")

        # A settle wait, not networkidle - a real SPA's analytics/tracking
        # requests can keep the network "busy" indefinitely, and networkidle
        # would just eat into a fixed timeout budget for no benefit; a fixed
        # wait after domcontentloaded is what the rest of this codebase
        # already uses for the same reason (see generic_adapter.py).
        await page.wait_for_timeout(_SETTLE_WAIT_MS)

        # Confirmed live against a real iCIMS posting (General Dynamics
        # Mission Systems): iCIMS renders the ENTIRE real job posting -
        # title, location, full description - inside a child <iframe>
        # (id="icims_content_iframe"); the top-level document.body is only
        # nav/footer chrome. Evaluating just `page` (as this used to)
        # returned real-looking but entirely wrong content (site
        # boilerplate, no job details at all, no location) rather than an
        # obvious empty/thin-content failure - a more dangerous failure
        # mode than Workday/Ashby's "returns nothing", since it wouldn't
        # have tripped worker.py's thin-content fallback trigger at all.
        # page.frames (Playwright's own frame tree, populated via CDP) can
        # read a frame's content regardless of same-origin policy - unlike
        # raw JS `iframe.contentDocument`, which same-origin-iframe-only
        # script on the page itself would be restricted by. A frame that
        # errors (still loading, cross-origin sandboxed, detached) is
        # skipped rather than failing the whole request.
        #
        # Child frames are ordered BEFORE the main frame, not just appended
        # after it - confirmed live on the same real iCIMS posting: even
        # once child-frame text was included at all, putting it last (after
        # several KB of the main frame's mega-menu site nav) still
        # measurably degraded extraction quality downstream (skills/
        # requirements came back nearly empty despite the real content
        # technically being present somewhere in the string) and left the
        # human-facing description field's own truncation
        # (backend/worker.py's _MAX_DESCRIPTION_CHARS) showing 100% nav
        # chrome, 0% real content. A site that goes to the trouble of
        # isolating job content in its own child iframe is reliably doing
        # so to separate it from generic site chrome - so child-frame text
        # is the higher-value content whenever both exist.
        child_texts = []
        main_text = ""
        for frame in page.frames:
            try:
                frame_text = await frame.evaluate(_VISIBLE_TEXT_JS)
            except Exception:
                continue
            if not frame_text:
                continue
            if frame == page.main_frame:
                main_text = frame_text
            else:
                child_texts.append(frame_text)

        return RenderResponse(success=True, text="\n".join(child_texts + ([main_text] if main_text else [])))
    finally:
        await context.close()


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "browser_ready": _browser is not None}
