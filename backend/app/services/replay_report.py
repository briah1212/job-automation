"""Builds a self-contained HTML replay report for a browser automation run.

The whole point: when a real ATS application fails on step 17 of 25, the
answer to "what happened and why" should never require reproducing the run
live. Every BrowserCheckpoint already carries everything needed - a
screenshot, a full DOM snapshot, why detect_state classified the page the
way it did, where every filled field's value came from, and the ordered
action log - this just assembles them into one browsable timeline.

Output is a single HTML file with screenshots embedded as base64 data URIs,
so it's portable (email it, attach it to a bug report, open it anywhere)
without needing MinIO access to view later.
"""
from __future__ import annotations

import base64
import html
import json
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.object_storage import get_browser_artifacts_storage
from app.models import BrowserCheckpoint, BrowserSession

_STATUS_COLORS = {
    "submitted": "#1a7f37",
    "manual_intervention": "#9a6700",
    "failed": "#cf222e",
}


def _fetch_bytes_safe(object_key: Optional[str]) -> Optional[bytes]:
    if not object_key:
        return None
    try:
        return get_browser_artifacts_storage().get_bytes(object_key)
    except Exception:
        return None


def _render_checkpoint(index: int, checkpoint: BrowserCheckpoint) -> str:
    screenshot_bytes = _fetch_bytes_safe(checkpoint.screenshot_object_key)
    screenshot_html = (
        f'<img class="screenshot" src="data:image/png;base64,{base64.b64encode(screenshot_bytes).decode()}" '
        f'alt="Screenshot at {html.escape(checkpoint.step)}">'
        if screenshot_bytes else '<div class="no-screenshot">No screenshot captured</div>'
    )

    dom_bytes = _fetch_bytes_safe(checkpoint.dom_snapshot_object_key)
    dom_html = html.escape(dom_bytes.decode("utf-8", errors="replace")) if dom_bytes else "No DOM snapshot captured"

    reasoning_json = html.escape(json.dumps(checkpoint.decision_reasoning or {}, indent=2))
    field_sources_rows = "".join(
        f"<tr><td>{html.escape(field)}</td><td>{html.escape(source)}</td></tr>"
        for field, source in (checkpoint.field_sources or {}).items()
    ) or '<tr><td colspan="2" class="muted">No fields filled at this checkpoint</td></tr>'

    actions_rows = "".join(
        f"<li><code>{html.escape(str(action.get('action', '?')))}</code> "
        f"{html.escape(json.dumps({k: v for k, v in action.items() if k != 'action'}))}</li>"
        for action in (checkpoint.action_log or [])
    ) or "<li class='muted'>No actions logged yet at this checkpoint</li>"

    filled_fields_rows = "".join(
        f"<tr><td>{html.escape(field)}</td><td>{html.escape(str(value))}</td></tr>"
        for field, value in (checkpoint.filled_fields or {}).items()
    ) or '<tr><td colspan="2" class="muted">None filled yet</td></tr>'

    return f"""
    <section class="checkpoint" id="checkpoint-{index}">
        <h2>#{index} - {html.escape(checkpoint.step)}</h2>
        <div class="meta">
            <span>{checkpoint.created_at.isoformat()}</span>
            <span>page {checkpoint.page_number}</span>
            <a href="{html.escape(checkpoint.url)}" target="_blank" rel="noopener">{html.escape(checkpoint.url)}</a>
        </div>
        <div class="grid">
            <div class="col">
                {screenshot_html}
            </div>
            <div class="col">
                <h3>Why this state was detected</h3>
                <pre class="reasoning">{reasoning_json}</pre>
                <h3>Filled fields (redacted)</h3>
                <table><tr><th>Field</th><th>Value</th></tr>{filled_fields_rows}</table>
                <h3>Field value sources</h3>
                <table><tr><th>Field</th><th>Source</th></tr>{field_sources_rows}</table>
                <h3>Actions taken so far this run</h3>
                <ul class="actions">{actions_rows}</ul>
            </div>
        </div>
        <details class="dom-details">
            <summary>DOM snapshot ({len(dom_bytes) if dom_bytes else 0} bytes)</summary>
            <pre class="dom">{dom_html}</pre>
        </details>
    </section>
    """


def build_replay_report(db: Session, browser_session_id: UUID) -> str:
    """Returns a complete, self-contained HTML document for the given session."""
    session = db.query(BrowserSession).filter(BrowserSession.id == browser_session_id).first()
    if session is None:
        raise ValueError(f"No browser_session found with id {browser_session_id}")

    checkpoints = (
        db.query(BrowserCheckpoint)
        .filter(BrowserCheckpoint.session_id == browser_session_id)
        .order_by(BrowserCheckpoint.created_at.asc())
        .all()
    )

    status_color = _STATUS_COLORS.get(session.status.value if session.status else "", "#57606a")
    checkpoints_html = "".join(_render_checkpoint(i + 1, cp) for i, cp in enumerate(checkpoints))
    toc = "".join(
        f'<a href="#checkpoint-{i + 1}">{i + 1}. {html.escape(cp.step)}</a>'
        for i, cp in enumerate(checkpoints)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Replay: {html.escape(session.session_key)}</title>
<style>
  body {{ font-family: -apple-system, sans-serif; margin: 0; padding: 0; background: #f6f8fa; color: #1f2328; }}
  header {{ background: white; padding: 20px 32px; border-bottom: 1px solid #d0d7de; position: sticky; top: 0; z-index: 10; }}
  header h1 {{ margin: 0 0 4px; font-size: 20px; }}
  header .status {{ display: inline-block; padding: 2px 10px; border-radius: 12px; color: white; font-size: 13px; background: {status_color}; }}
  nav {{ padding: 12px 32px; background: white; border-bottom: 1px solid #d0d7de; display: flex; gap: 12px; flex-wrap: wrap; font-size: 13px; }}
  nav a {{ color: #0969da; text-decoration: none; }}
  .checkpoint {{ background: white; margin: 20px 32px; border: 1px solid #d0d7de; border-radius: 8px; padding: 20px; }}
  .checkpoint h2 {{ margin-top: 0; }}
  .meta {{ display: flex; gap: 16px; font-size: 13px; color: #57606a; margin-bottom: 16px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  @media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  .screenshot {{ max-width: 100%; border: 1px solid #d0d7de; border-radius: 6px; }}
  .no-screenshot {{ padding: 40px; text-align: center; color: #57606a; background: #f6f8fa; border-radius: 6px; }}
  h3 {{ font-size: 13px; text-transform: uppercase; color: #57606a; margin: 16px 0 6px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 8px; }}
  table th, table td {{ text-align: left; padding: 4px 8px; border-bottom: 1px solid #eaeef2; }}
  .muted {{ color: #8c959f; font-style: italic; }}
  pre.reasoning {{ background: #f6f8fa; padding: 10px; border-radius: 6px; font-size: 12px; overflow-x: auto; max-height: 200px; }}
  ul.actions {{ font-size: 13px; padding-left: 18px; }}
  ul.actions code {{ background: #f6f8fa; padding: 1px 5px; border-radius: 4px; }}
  .dom-details {{ margin-top: 16px; }}
  .dom-details summary {{ cursor: pointer; font-size: 13px; color: #57606a; }}
  pre.dom {{ background: #f6f8fa; padding: 10px; border-radius: 6px; font-size: 11px; overflow-x: auto; max-height: 400px; white-space: pre-wrap; word-break: break-all; }}
</style>
</head>
<body>
<header>
    <h1>Replay: {html.escape(session.session_key)}</h1>
    <span class="status">{html.escape(session.status.value if session.status else "unknown")}</span>
    {f'<span style="margin-left:12px; color:#57606a; font-size:13px;">pause reason: {html.escape(session.pause_reason.value)}</span>' if session.pause_reason else ""}
</header>
<nav>{toc}</nav>
{checkpoints_html if checkpoints else '<p style="margin:32px;">No checkpoints recorded for this session.</p>'}
</body>
</html>"""
