import os
import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

_API_URL = os.environ.get("API_URL", "http://api:8000")
_INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")
_TIMEOUT_SECONDS = 15.0


class CredentialVaultError(Exception):
    """Raised when the internal credential vault endpoint call fails."""


async def get_or_create_credential(
    user_id: str, ats_platform: str, tenant_key: str, email: str
) -> Dict[str, Any]:
    """Fetch or create an ATS account credential via the backend's internal endpoint.

    browser-worker never holds CREDENTIAL_ENCRYPTION_KEY and never decrypts
    anything itself - this one HTTP call, authenticated with INTERNAL_API_KEY,
    is the only place a plaintext ATS password reaches this process, and only
    for the one tenant being processed right now.
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
        try:
            response = await client.post(
                f"{_API_URL}/api/internal/ats-credentials/get-or-create",
                headers={"X-Internal-Api-Key": _INTERNAL_API_KEY},
                json={
                    "user_id": user_id,
                    "ats_platform": ats_platform,
                    "tenant_key": tenant_key,
                    "email": email,
                },
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            logger.error("Credential vault get-or-create failed: %s - %s", exc.response.status_code, exc.response.text)
            raise CredentialVaultError(f"get-or-create failed: {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            logger.error("Credential vault get-or-create request error: %s", exc)
            raise CredentialVaultError(f"get-or-create request error: {exc}") from exc


async def mark_credential_status(credential_id: str, status: str) -> None:
    """Update a credential's lifecycle status (e.g. "login_failed") via the internal endpoint."""
    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
        try:
            response = await client.post(
                f"{_API_URL}/api/internal/ats-credentials/{credential_id}/mark-status",
                headers={"X-Internal-Api-Key": _INTERNAL_API_KEY},
                json={"status": status},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("Credential vault mark-status failed: %s - %s", exc.response.status_code, exc.response.text)
            raise CredentialVaultError(f"mark-status failed: {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            logger.error("Credential vault mark-status request error: %s", exc)
            raise CredentialVaultError(f"mark-status request error: {exc}") from exc
