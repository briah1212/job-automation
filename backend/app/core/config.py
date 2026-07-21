from __future__ import annotations

from typing import Any
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)
    
    # App
    app_name: str = "Job Automation Platform"
    debug: bool = False
    
    # Database
    database_url: str

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173", "http://localhost:3002"]

    # Object storage (MinIO / S3-compatible)
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_browser_bucket: str = "browser-artifacts"

    # ATS credential vault - deliberately separate from secret_key/jwt so a
    # JWT secret leak doesn't also compromise every stored third-party password.
    # Defaults to "" (not required) because Settings() is instantiated on
    # import by every process that touches app.core.database, including
    # browser-worker - which must never actually hold this key (see
    # docs/browser-state-machine-design.md section 8). Only `api` sets a real
    # value; get_credential_cipher() fails loudly if ever called without one.
    credential_encryption_key: str = ""

    # Shared secret for service-to-service calls from browser-worker (e.g. the
    # credential vault endpoints) - required because `api` publishes its port
    # to the host, so these routes are not protected by Docker network isolation
    # alone, and must not be reachable by a regular authenticated user.
    internal_api_key: str


settings = Settings()
