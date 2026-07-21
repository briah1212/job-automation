import logging
import json
import re
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from playwright.async_api import Page
from ..models import Checkpoint

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manage checkpoints for browser sessions.

    When constructed with a `db` session and `browser_session_id`, checkpoints
    are written durably to Postgres (BrowserCheckpoint rows) and MinIO
    (screenshots) via the backend's models/object storage client - this is
    what queue_worker.py uses in production, so a container restart or crash
    doesn't lose in-flight session state.

    When constructed without them, checkpoints fall back to local JSON files
    under checkpoint_dir - this path exists only for worker.py's standalone
    host-based demo entrypoint (run_demo.sh), which has no database access.
    """

    def __init__(
        self,
        checkpoint_dir: str = "/tmp/checkpoints",
        db=None,
        browser_session_id: Optional[uuid.UUID] = None,
    ):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._db = db
        self._browser_session_id = browser_session_id

    @property
    def _durable(self) -> bool:
        return self._db is not None and self._browser_session_id is not None

    async def create_checkpoint(
        self,
        session_id: str,
        page: Page,
        step: str,
        filled_fields: dict,
        page_number: int = 1,
        decision_reasoning: Optional[dict] = None,
        field_sources: Optional[dict] = None,
        action_log: Optional[list] = None,
    ) -> Checkpoint:
        """Save a checkpoint: URL, screenshot, DOM snapshot, redacted filled
        fields, form state, timestamp, plus a replay/debug trail (why this
        state was detected, where each field's value came from, what
        actions were taken) - see services/replay_report.py, which is what
        actually reads decision_reasoning/field_sources/action_log back out.
        The last three are optional/best-effort: a caller that can't supply
        them (or a failure while capturing the DOM) must not block the
        resume-critical parts of a checkpoint from being written."""
        timestamp = datetime.utcnow()
        screenshot_bytes = await page.screenshot(full_page=True)
        dom_snapshot = await self._extract_dom_snapshot(page)
        raw_form_state = await self._extract_form_state(page)
        redacted_fields = self._redact_sensitive(filled_fields.copy())
        redacted_form_state = {
            form_key: self._redact_sensitive(form_fields)
            for form_key, form_fields in raw_form_state.items()
        }

        if self._durable:
            screenshot_ref = await self._store_screenshot_durable(session_id, step, timestamp, screenshot_bytes)
            dom_ref = await self._store_dom_snapshot_durable(session_id, step, timestamp, dom_snapshot)
            self._store_checkpoint_durable(
                step, page.url, screenshot_ref, dom_ref, redacted_fields, redacted_form_state, page_number,
                decision_reasoning or {}, field_sources or {}, action_log or [],
            )
        else:
            screenshot_ref = self._store_screenshot_local(session_id, step, timestamp, screenshot_bytes)
            self._store_checkpoint_local(session_id, step, timestamp, page.url, screenshot_ref, redacted_fields, redacted_form_state, page_number)

        checkpoint = Checkpoint(
            session_id=session_id,
            timestamp=timestamp,
            step=step,
            url=page.url,
            screenshot_path=screenshot_ref,
            filled_fields=redacted_fields,
            form_state=redacted_form_state,
            page_number=page_number,
        )
        logger.info(f"Created checkpoint {step} for session {session_id}")
        return checkpoint

    async def load_checkpoint(self, session_id: str) -> Optional[Checkpoint]:
        """Load the latest checkpoint for a session."""
        if self._durable:
            return self._load_checkpoint_durable(session_id)
        return self._load_checkpoint_local(session_id)

    def list_checkpoints(self, session_id: str) -> List[str]:
        """List all checkpoint steps for a session, oldest first."""
        if self._durable:
            return self._list_checkpoints_durable()

        session_dir = self.checkpoint_dir / session_id
        if not session_dir.exists():
            return []
        checkpoints = [f.stem for f in session_dir.glob("*.json") if f.name != "latest.json"]
        return sorted(checkpoints)

    # -- Durable (Postgres + MinIO) backend --

    async def _store_screenshot_durable(self, session_id: str, step: str, timestamp: datetime, data: bytes) -> Optional[str]:
        return await self._put_object_durable(session_id, step, timestamp, data, "png", "image/png")

    async def _store_dom_snapshot_durable(self, session_id: str, step: str, timestamp: datetime, html: str) -> Optional[str]:
        return await self._put_object_durable(session_id, step, timestamp, html.encode("utf-8"), "html", "text/html")

    async def _put_object_durable(
        self, session_id: str, step: str, timestamp: datetime, data: bytes, extension: str, content_type: str
    ) -> Optional[str]:
        """A checkpoint asset (screenshot/DOM snapshot) failing to upload must
        not abort the whole task - the resume-critical parts of a checkpoint
        (state, URL, filled_fields) have nothing to do with whether MinIO is
        reachable right now. Returns None on failure; the checkpoint row
        just gets a null object key for this asset rather than never being
        written at all."""
        from app.core.object_storage import get_browser_artifacts_storage

        object_key = f"{session_id}/{step}_{timestamp.strftime('%Y%m%d_%H%M%S')}.{extension}"
        try:
            get_browser_artifacts_storage().put_bytes(object_key, data, content_type=content_type)
            return object_key
        except Exception as exc:
            logger.warning(f"Failed to upload {extension} checkpoint asset to MinIO (checkpoint still saved): {exc}")
            return None

    def _store_checkpoint_durable(
        self, step: str, url: str, screenshot_object_key: Optional[str], dom_snapshot_object_key: Optional[str],
        filled_fields: dict, form_state: dict, page_number: int,
        decision_reasoning: dict, field_sources: dict, action_log: list,
    ) -> None:
        from app.models import BrowserCheckpoint

        row = BrowserCheckpoint(
            session_id=self._browser_session_id,
            browser_state=step,
            step=step,
            url=url,
            screenshot_object_key=screenshot_object_key,
            dom_snapshot_object_key=dom_snapshot_object_key,
            filled_fields=filled_fields,
            form_state=form_state,
            page_number=page_number,
            decision_reasoning=decision_reasoning,
            field_sources=field_sources,
            action_log=action_log,
        )
        self._db.add(row)
        self._db.commit()

    def _load_checkpoint_durable(self, session_id: str) -> Optional[Checkpoint]:
        from app.models import BrowserCheckpoint

        row = (
            self._db.query(BrowserCheckpoint)
            .filter(BrowserCheckpoint.session_id == self._browser_session_id)
            .order_by(BrowserCheckpoint.created_at.desc())
            .first()
        )
        if row is None:
            logger.warning(f"No checkpoint found for session {session_id}")
            return None

        logger.info(f"Loaded checkpoint for session {session_id}")
        return Checkpoint(
            session_id=session_id,
            timestamp=row.created_at,
            step=row.step,
            url=row.url,
            screenshot_path=row.screenshot_object_key or "",
            filled_fields=row.filled_fields,
            form_state=row.form_state,
            page_number=row.page_number,
        )

    def _list_checkpoints_durable(self) -> List[str]:
        from app.models import BrowserCheckpoint

        rows = (
            self._db.query(BrowserCheckpoint)
            .filter(BrowserCheckpoint.session_id == self._browser_session_id)
            .order_by(BrowserCheckpoint.created_at.asc())
            .all()
        )
        return [row.step for row in rows]

    # -- Local file backend (host-based demo only) --

    def _store_screenshot_local(self, session_id: str, step: str, timestamp: datetime, data: bytes) -> str:
        session_dir = self.checkpoint_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = session_dir / f"{step}_{timestamp.strftime('%Y%m%d_%H%M%S')}.png"
        screenshot_path.write_bytes(data)
        return str(screenshot_path)

    def _store_checkpoint_local(
        self, session_id: str, step: str, timestamp: datetime, url: str, screenshot_path: str,
        filled_fields: dict, form_state: dict, page_number: int,
    ) -> None:
        session_dir = self.checkpoint_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        checkpoint = Checkpoint(
            session_id=session_id,
            timestamp=timestamp,
            step=step,
            url=url,
            screenshot_path=screenshot_path,
            filled_fields=filled_fields,
            form_state=form_state,
            page_number=page_number,
        )

        checkpoint_file = session_dir / f"{step}_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint.model_dump(mode="json"), f, indent=2, default=str)

        latest_file = session_dir / "latest.json"
        with open(latest_file, "w") as f:
            json.dump(checkpoint.model_dump(mode="json"), f, indent=2, default=str)

    def _load_checkpoint_local(self, session_id: str) -> Optional[Checkpoint]:
        session_dir = self.checkpoint_dir / session_id
        latest_file = session_dir / "latest.json"

        if not latest_file.exists():
            logger.warning(f"No checkpoint found for session {session_id}")
            return None

        with open(latest_file, "r") as f:
            data = json.load(f)
            checkpoint = Checkpoint(**data)

        logger.info(f"Loaded checkpoint for session {session_id}")
        return checkpoint

    # -- Shared helpers --

    async def _extract_dom_snapshot(self, page: Page) -> str:
        """Full rendered HTML at this checkpoint - what detect_state/inspect_form
        actually saw, independent of the screenshot (a screenshot shows what
        a human would see; this shows what the adapter's selectors saw,
        which is what actually matters for debugging a misclassification or
        a selector that didn't match)."""
        try:
            return await page.content()
        except Exception as exc:
            logger.warning(f"Failed to capture DOM snapshot (non-fatal): {exc}")
            return ""

    async def _extract_form_state(self, page: Page) -> Dict[str, Any]:
        """Extract current form state"""
        try:
            form_state = await page.evaluate("""
                () => {
                    const forms = document.querySelectorAll('form');
                    const state = {};

                    forms.forEach((form, idx) => {
                        const formData = {};
                        const inputs = form.querySelectorAll('input, select, textarea');

                        inputs.forEach(input => {
                            const name = input.name || input.id;
                            if (name && input.type !== 'password' && input.type !== 'file') {
                                if (input.type === 'checkbox') {
                                    formData[name] = input.checked;
                                } else if (input.type === 'radio') {
                                    if (input.checked) {
                                        formData[name] = input.value;
                                    }
                                } else {
                                    formData[name] = input.value;
                                }
                            }
                        });

                        state[`form_${idx}`] = formData;
                    });

                    return state;
                }
            """)
            return form_state
        except Exception as e:
            logger.error(f"Error extracting form state: {e}")
            return {}

    def _redact_sensitive(self, fields: dict) -> dict:
        """Redact sensitive field values by name, with a value-pattern check
        as defense in depth for fields whose name doesn't give it away.

        The name-keyword list was previously narrow enough to miss real PII
        field names real ATS forms use (date of birth, national/government
        ID, bank details) - anything not on the list was written to Postgres
        in plaintext. Broadened here; the value-pattern check additionally
        catches an SSN- or card-shaped value sitting in a genuinely generic
        field (e.g. a free-text "additional notes" box) that no name-based
        list could ever fully anticipate.
        """
        sensitive_keys = [
            "password", "passwd", "pwd",
            "ssn", "social_security", "social_insurance",
            "credit_card", "card_number", "cvv", "cvc", "security_code",
            "pin",
            "date_of_birth", "dob", "birth_date", "birthdate",
            "national_id", "nationalid", "passport",
            "drivers_license", "driver_license", "driving_license", "license_number",
            "bank_account", "account_number", "routing_number", "iban", "swift",
            "tax_id", "taxid", "ein", "itin",
        ]

        redacted = {}
        for key, value in fields.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                redacted[key] = "[REDACTED]"
            elif self._looks_like_sensitive_value(value):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = value

        return redacted

    @staticmethod
    def _looks_like_sensitive_value(value: Any) -> bool:
        """Value-shape check independent of field name - an SSN or card
        number typed into a genuinely generic field (free-text notes, an
        unmapped custom question) would otherwise slip past name-based
        redaction entirely."""
        if not isinstance(value, str):
            return False
        digits_only = re.sub(r"[\s-]", "", value)
        if not digits_only.isdigit():
            return False
        # SSN (9 digits) or a plausible card number (13-19 digits) - both
        # ranges intentionally wide rather than validating a real checksum,
        # since a false-positive redaction is a far cheaper mistake than a
        # false-negative leak here.
        return len(digits_only) == 9 or 13 <= len(digits_only) <= 19
