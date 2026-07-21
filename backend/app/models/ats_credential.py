from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, LargeBinary, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class AtsCredentialStatus(str, enum.Enum):
    """Lifecycle status of a stored ATS account credential."""
    active = "active"
    needs_verification = "needs_verification"
    revoked = "revoked"
    login_failed = "login_failed"


class AtsCredential(Base):
    """An automatically-created ATS account credential, scoped per (user, platform, tenant).

    encrypted_password is opaque ciphertext produced by a CredentialCipher
    implementation (see app.core.credential_cipher) - this model never sees
    or stores a plaintext password.
    """

    __tablename__ = "ats_credentials"
    __table_args__ = (
        UniqueConstraint("user_id", "ats_platform", "tenant_key", name="uq_ats_credentials_user_platform_tenant"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    ats_platform = Column(String, nullable=False)
    tenant_key = Column(String, nullable=False)
    email = Column(String, nullable=False)
    encrypted_password = Column(LargeBinary, nullable=False)

    status = Column(Enum(AtsCredentialStatus), nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)

    user = relationship("User")
