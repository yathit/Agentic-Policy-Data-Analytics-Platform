"""
Pytest configuration and fixtures for testing.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.models import dataset  # noqa: F401 - Import to register models
from app.models import run  # noqa: F401 - Import to register run models
from app.main import app


# Test database engine
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Test session factory
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    """Override database dependency for testing."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def test_db():
    """
    Create a fresh in-memory SQLite database for each test.

    Yields:
        SQLAlchemy Session for testing
    """
    # Create all tables
    Base.metadata.create_all(bind=test_engine)

    # Create session
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(test_db):
    """
    Create a test client with database dependency override.

    Args:
        test_db: Test database session fixture

    Yields:
        FastAPI TestClient
    """
    # Override the database dependency
    app.dependency_overrides[get_db] = override_get_db

    # Create tables
    Base.metadata.create_all(bind=test_engine)

    with TestClient(app) as test_client:
        yield test_client

    # Clean up
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
