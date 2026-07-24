"""Tests for render_server's multi-frame text extraction.

Confirmed live against a real iCIMS posting (General Dynamics Mission
Systems, careers-gdms.icims.com): the entire real job posting - title,
location, full description - renders inside a child <iframe>, not the
top-level document.body. Reading only the top frame silently returned
real-looking but entirely wrong content (site nav/footer boilerplate, no
job details, no location) instead of an obvious empty/thin-content
failure - more dangerous than an empty-page failure since nothing else in
the pipeline would catch it.
"""
import pytest
from playwright.async_api import async_playwright

from browser_worker.render_server import _VISIBLE_TEXT_JS


async def _extract_all_frames(html: str) -> str:
    """Mirrors /render's own frame-collection logic in render_server.py:
    child frames first, main frame last."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html)
        # Mirrors render's own settle-wait purpose: give the iframe a beat
        # to finish loading its srcdoc content before extracting.
        await page.wait_for_timeout(200)
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
        await browser.close()
        return "\n".join(child_texts + ([main_text] if main_text else []))


class TestMultiFrameExtraction:
    @pytest.mark.asyncio
    async def test_child_frame_content_is_captured(self):
        """The iCIMS shape: top-level page is only nav chrome, the real
        content lives in a child frame."""
        html = (
            '<body>'
            '<nav>Site Navigation Chrome</nav>'
            '<iframe srcdoc="<body>Software Engineer - Dedham, Massachusetts. Real job description text.</body>"></iframe>'
            '</body>'
        )
        result = await _extract_all_frames(html)
        assert "Site Navigation Chrome" in result
        assert "Software Engineer - Dedham, Massachusetts" in result

    @pytest.mark.asyncio
    async def test_no_iframe_still_captures_top_frame(self):
        """Every previously-working platform (no iframe at all) must see
        zero behavior change."""
        html = "<body>Plain job posting with no iframe.</body>"
        result = await _extract_all_frames(html)
        assert "Plain job posting with no iframe." in result

    @pytest.mark.asyncio
    async def test_script_and_style_excluded_in_child_frame(self):
        """_VISIBLE_TEXT_JS's script/style stripping applies per-frame, not
        just to the top-level document - a child frame's own SPA hydration
        payload shouldn't leak into extracted text either."""
        html = (
            '<body>'
            '<iframe srcdoc="<body><script>window.__DATA__={secret:1};</script>'
            '<style>.x{color:red}</style>Real visible text</body>"></iframe>'
            '</body>'
        )
        result = await _extract_all_frames(html)
        assert "Real visible text" in result
        assert "__DATA__" not in result
        assert "color:red" not in result

    @pytest.mark.asyncio
    async def test_child_frame_content_ordered_before_main_frame(self):
        """Confirmed live: even with child-frame text included at all,
        putting it AFTER several KB of main-frame nav chrome still
        measurably degraded downstream extraction quality, and left
        backend/worker.py's own truncated description field showing 100%
        chrome, 0% real content. Child-frame text must come first."""
        html = (
            '<body>'
            '<nav>MAIN FRAME CHROME</nav>'
            '<iframe srcdoc="<body>CHILD FRAME REAL CONTENT</body>"></iframe>'
            '</body>'
        )
        result = await _extract_all_frames(html)
        assert result.index("CHILD FRAME REAL CONTENT") < result.index("MAIN FRAME CHROME")
