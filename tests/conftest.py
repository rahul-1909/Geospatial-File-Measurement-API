import os
import sys
from pathlib import Path

# Add project root directory to sys.path for test runners
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.session import Base, get_db
from app.core.config import settings

# Use in-memory SQLite database for isolated test execution
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    """Create fresh in-memory database for each test."""
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session, tmp_path: Path):
    """TestClient that uses the test in-memory database and an isolated temp uploads directory."""
    # Temporarily point settings.UPLOAD_DIR to tmp_path
    orig_upload_dir = settings.UPLOAD_DIR
    settings.UPLOAD_DIR = tmp_path

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    settings.UPLOAD_DIR = orig_upload_dir


@pytest.fixture
def sample_data_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "sample_data"
