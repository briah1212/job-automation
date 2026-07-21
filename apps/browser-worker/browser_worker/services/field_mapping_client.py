import os
import logging
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)

_API_URL = os.environ.get("API_URL", "http://api:8000")
_INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")
_TIMEOUT_SECONDS = 10.0


async def lookup_mappings(ats_platform: str, domain: str, form_fingerprint: str) -> Dict[str, str]:
    """Fetch previously learned {field_name: canonical_name} mappings for this
    exact form shape. Best-effort: returns {} on any failure rather than
    raising, since a durable-mapping lookup failing should degrade to the
    regular FieldMapper regex path, not break form filling."""
    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
        try:
            response = await client.post(
                f"{_API_URL}/api/internal/field-mappings/lookup",
                headers={"X-Internal-Api-Key": _INTERNAL_API_KEY},
                json={"ats_platform": ats_platform, "domain": domain, "form_fingerprint": form_fingerprint},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            logger.warning(f"Field mapping lookup failed (degrading to regex-only): {exc}")
            return {}


async def record_mapping(
    ats_platform: str, domain: str, form_fingerprint: str, field_name: str, label: Optional[str], canonical_name: str, source: str = "learned"
) -> None:
    """Best-effort, fire-and-forget: a failure here must never break form filling."""
    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
        try:
            response = await client.post(
                f"{_API_URL}/api/internal/field-mappings/record",
                headers={"X-Internal-Api-Key": _INTERNAL_API_KEY},
                json={
                    "ats_platform": ats_platform,
                    "domain": domain,
                    "form_fingerprint": form_fingerprint,
                    "field_name": field_name,
                    "label": label,
                    "canonical_name": canonical_name,
                    "source": source,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(f"Failed to record learned field mapping for {field_name} (non-fatal): {exc}")
