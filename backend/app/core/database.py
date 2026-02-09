"""
Database connection and session management for Policy Analytics Platform.
"""

import uuid
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.core.config import settings

# Create database engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Verify connections before using
    echo=settings.debug,  # Log SQL in debug mode
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative base for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session.

    Usage in FastAPI endpoints:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_run_status_enum() -> None:
    """
    Normalize run_status enum labels to lowercase values expected by RunStatus.

    Legacy databases may contain uppercase labels (e.g. AWAITING_APPROVAL).
    This migration rebuilds the enum and remaps existing rows to lowercase.
    """
    from sqlalchemy import text

    desired_labels = [
        "planning",
        "awaiting_approval",
        "queued",
        "running",
        "completed",
        "failed",
        "aborted",
    ]

    with engine.begin() as conn:
        type_exists = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1
                FROM pg_type
                WHERE typname = 'run_status'
            )
        """)).scalar()

        if not type_exists:
            return

        rows = conn.execute(text("""
            SELECT enumlabel
            FROM pg_enum
            WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'run_status')
            ORDER BY enumsortorder
        """)).fetchall()
        current_labels = [row[0] for row in rows]

        if current_labels == desired_labels:
            return

        has_uppercase_legacy = any(label != label.lower() for label in current_labels)
        missing_desired = any(label not in current_labels for label in desired_labels)

        if not has_uppercase_legacy and not missing_desired:
            return

        temp_type = f"run_status_old_{uuid.uuid4().hex[:8]}"

        conn.execute(text(f"ALTER TYPE run_status RENAME TO {temp_type}"))
        conn.execute(text(
            "CREATE TYPE run_status AS ENUM "
            "('planning', 'awaiting_approval', 'queued', 'running', 'completed', 'failed', 'aborted')"
        ))

        conn.execute(text("ALTER TABLE runs ALTER COLUMN status DROP DEFAULT"))
        conn.execute(text(f"""
            ALTER TABLE runs
            ALTER COLUMN status TYPE run_status
            USING (
                CASE status::text
                    WHEN 'PLANNING' THEN 'planning'
                    WHEN 'AWAITING_APPROVAL' THEN 'awaiting_approval'
                    WHEN 'QUEUED' THEN 'queued'
                    WHEN 'RUNNING' THEN 'running'
                    WHEN 'COMPLETED' THEN 'completed'
                    WHEN 'FAILED' THEN 'failed'
                    WHEN 'ABORTED' THEN 'aborted'
                    WHEN 'NEEDS_APPROVAL' THEN 'awaiting_approval'
                    WHEN 'needs_approval' THEN 'awaiting_approval'
                    ELSE lower(status::text)
                END
            )::run_status
        """))
        conn.execute(text(
            "ALTER TABLE runs ALTER COLUMN status SET DEFAULT 'awaiting_approval'::run_status"
        ))

        remaining_refs = conn.execute(text("""
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE udt_name = :temp_type
        """), {"temp_type": temp_type}).scalar()

        if remaining_refs == 0:
            conn.execute(text(f"DROP TYPE {temp_type}"))


def init_db() -> None:
    """
    Initialize database tables.
    Called on application startup.
    """
    # Import all models here to ensure they are registered with Base
    from app.models import dataset  # noqa: F401
    from app.models import run  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Run enum migrations after tables exist
    try:
        _migrate_run_status_enum()
    except Exception as e:
        # Log but don't fail startup - enum might already exist
        import logging
        logging.getLogger(__name__).warning(f"Enum migration warning: {e}")
