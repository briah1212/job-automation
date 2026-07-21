from __future__ import annotations

import secrets
import string
import uuid
from datetime import datetime
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.core.credential_cipher import CredentialCipher
from app.models import AtsCredential, AtsCredentialStatus

_PASSWORD_LENGTH = 20
_PASSWORD_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*-_="


def generate_secure_password(length: int = _PASSWORD_LENGTH) -> str:
    """A high-entropy password meant to satisfy virtually any real password policy.

    This is a generic default, not tailored to any specific ATS's rules -
    inspecting a create-account form's actual validation constraints requires
    DOM access, which only browser-worker has. If a target site rejects this
    password, that's a Phase 3/4 retry concern, not something this function
    can know about in advance.
    """
    while True:
        password = "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))
        # Guarantee at least one of each character class, since some sites
        # reject an all-random string that happens to miss a class by chance.
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in "!@#$%^&*-_=" for c in password)
        ):
            return password


def get_or_create_credential(
    db: Session,
    cipher: CredentialCipher,
    user_id: uuid.UUID,
    ats_platform: str,
    tenant_key: str,
    email: str,
) -> Dict[str, Any]:
    """Fetch the existing credential for (user, platform, tenant), or create one.

    Never generates a second credential for a tenant that already has one, even
    if that one's status is login_failed/needs_verification - callers (the
    future account-creation state handler) are expected to branch on `status`
    rather than silently retry-by-creating, per the design doc's "reuse and
    staleness" policy: a second auto-created account on the same tenant is
    itself a risk (clutter, possible duplicate-application flags on the ATS).
    """
    existing = (
        db.query(AtsCredential)
        .filter(
            AtsCredential.user_id == user_id,
            AtsCredential.ats_platform == ats_platform,
            AtsCredential.tenant_key == tenant_key,
        )
        .first()
    )

    if existing is not None:
        existing.last_used_at = datetime.utcnow()
        db.commit()
        return {
            "credential_id": str(existing.id),
            "email": existing.email,
            "password": cipher.decrypt(existing.encrypted_password),
            "status": existing.status.value,
            "created": False,
        }

    password = generate_secure_password()
    credential = AtsCredential(
        user_id=user_id,
        ats_platform=ats_platform,
        tenant_key=tenant_key,
        email=email,
        encrypted_password=cipher.encrypt(password),
        status=AtsCredentialStatus.active,
        last_used_at=datetime.utcnow(),
    )
    db.add(credential)
    db.commit()
    db.refresh(credential)

    return {
        "credential_id": str(credential.id),
        "email": credential.email,
        "password": password,
        "status": credential.status.value,
        "created": True,
    }


def mark_credential_status(db: Session, credential_id: uuid.UUID, status: AtsCredentialStatus) -> bool:
    """Update a credential's status (e.g. login_failed after a failed login attempt).

    Returns False if no matching credential row exists, so callers can
    distinguish "not found" from a successful update.
    """
    credential = db.query(AtsCredential).filter(AtsCredential.id == credential_id).first()
    if credential is None:
        return False
    credential.status = status
    db.commit()
    return True
