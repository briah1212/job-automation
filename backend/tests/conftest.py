from __future__ import annotations

import os

# The test suite must stay hermetic regardless of which AI provider the
# actual running app is configured to use - AIGateway/BaseAgent default to
# os.getenv("AI_PROVIDER") when no provider is passed explicitly, so without
# this, flipping the deployment's real AI_PROVIDER (e.g. mock -> deepseek)
# silently makes every test that constructs an agent without an explicit
# provider start making real, billed, non-deterministic API calls. Set at
# import time (before any test module or fixture runs) so it's already in
# place for every agent constructed anywhere in the suite.
os.environ["AI_PROVIDER"] = "mock"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from main import app

# Use a dedicated Postgres test database (reachable at the `postgres` service on the
# Docker network). SQLite cannot compile Postgres-specific types used by Phase 3 models
# (JSONB, ARRAY), so tests must run against real Postgres.
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:postgres@postgres:5432/job_automation_test"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    """Create a test database."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db):
    """Create a test client."""
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
