import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from playwright.async_api import Page
from ..models import Checkpoint

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manage checkpoints for browser sessions"""

    def __init__(self, checkpoint_dir: str = "/tmp/checkpoints"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    async def create_checkpoint(
        self,
        session_id: str,
        page: Page,
        step: str,
        filled_fields: dict,
        page_number: int = 1,
    ) -> Checkpoint:
        """
        Save checkpoint:
        - Current URL
        - Screenshot
        - Filled fields (redact sensitive)
        - Form state
        - Timestamp
        """
        timestamp = datetime.now()
        
        # Create session directory
        session_dir = self.checkpoint_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # Save screenshot
        screenshot_filename = f"{step}_{timestamp.strftime('%Y%m%d_%H%M%S')}.png"
        screenshot_path = session_dir / screenshot_filename
        await page.screenshot(path=str(screenshot_path), full_page=True)

        # Get form state
        form_state = await self._extract_form_state(page)

        # Redact sensitive fields
        redacted_fields = self._redact_sensitive(filled_fields.copy())

        # Create checkpoint
        checkpoint = Checkpoint(
            session_id=session_id,
            timestamp=timestamp,
            step=step,
            url=page.url,
            screenshot_path=str(screenshot_path),
            filled_fields=redacted_fields,
            form_state=form_state,
            page_number=page_number,
        )

        # Save checkpoint metadata
        checkpoint_file = session_dir / f"{step}_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint.model_dump(mode="json"), f, indent=2, default=str)

        # Save latest checkpoint
        latest_file = session_dir / "latest.json"
        with open(latest_file, "w") as f:
            json.dump(checkpoint.model_dump(mode="json"), f, indent=2, default=str)

        logger.info(f"Created checkpoint {step} for session {session_id}")
        return checkpoint

    async def load_checkpoint(self, session_id: str) -> Optional[Checkpoint]:
        """Load latest checkpoint"""
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

    def list_checkpoints(self, session_id: str) -> List[str]:
        """List all checkpoints for a session"""
        session_dir = self.checkpoint_dir / session_id
        
        if not session_dir.exists():
            return []

        checkpoints = []
        for file in session_dir.glob("*.json"):
            if file.name != "latest.json":
                checkpoints.append(file.stem)

        return sorted(checkpoints)

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
        """Redact sensitive field values"""
        sensitive_keys = [
            "password",
            "ssn",
            "social_security",
            "credit_card",
            "cvv",
            "pin",
        ]
        
        redacted = {}
        for key, value in fields.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = value
        
        return redacted
