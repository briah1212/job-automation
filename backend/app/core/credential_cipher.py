from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class CredentialCipher(ABC):
    """Encrypts/decrypts ATS account credentials at rest.

    This is the seam a real secret manager (Vault, AWS Secrets Manager, GCP
    Secret Manager) drops in behind later - callers only ever depend on this
    interface, never on FernetCredentialCipher directly, so that swap requires
    no changes to app.services.ats_credential_vault or its callers.
    """

    @abstractmethod
    def encrypt(self, plaintext: str) -> bytes: ...

    @abstractmethod
    def decrypt(self, ciphertext: bytes) -> str: ...


class FernetCredentialCipher(CredentialCipher):
    """Local/dev implementation: symmetric encryption keyed by CREDENTIAL_ENCRYPTION_KEY.

    Not implemented in this phase: a VaultCredentialCipher/AWSSecretsManagerCipher
    variant that stores the key itself in a real secret manager rather than an
    environment variable - deliberately deferred per instruction not to block
    this work on secret-manager integration.
    """

    def __init__(self, key: str):
        self._fernet = Fernet(key.encode())

    def encrypt(self, plaintext: str) -> bytes:
        return self._fernet.encrypt(plaintext.encode())

    def decrypt(self, ciphertext: bytes) -> str:
        try:
            return self._fernet.decrypt(ciphertext).decode()
        except InvalidToken as exc:
            raise ValueError("Could not decrypt credential - wrong key or corrupted ciphertext") from exc


_cipher: Optional[CredentialCipher] = None


def get_credential_cipher() -> CredentialCipher:
    """Lazily-constructed singleton, matching the pattern in app.core.object_storage."""
    global _cipher
    if _cipher is None:
        _cipher = FernetCredentialCipher(settings.credential_encryption_key)
    return _cipher
