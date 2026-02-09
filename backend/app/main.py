"""Main FastAPI application."""
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text

from app.api.routes import health
from app.api.routes import runs
from app.api.routes import ws
from app.api.errors import (
    APIException,
    api_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.core.config import settings
from app.core.database import init_db, SessionLocal

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware - added immediately after app creation to ensure all responses have CORS headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _is_data_gov_sg_collection_empty() -> bool:
    """Check if data_gov_sg_collection table is empty."""
    db = SessionLocal()
    try:
        result = db.execute(
            text("SELECT EXISTS(SELECT 1 FROM data_gov_sg_collection LIMIT 1)")
        )
        exists = result.scalar()
        return not exists
    except Exception as e:
        logger.warning("Failed to check data_gov_sg_collection table: %s", e)
        return False
    finally:
        db.close()


def _bootstrap_data_gov_sg_ingest() -> None:
    """Enqueue data.gov.sg ingest if table is empty (startup bootstrap)."""
    if not settings.data_gov_sg_ingest_startup_if_empty:
        return

    if _is_data_gov_sg_collection_empty():
        logger.info("data_gov_sg_collection is empty, enqueueing bootstrap ingest")
        from app.tasks.data_gov_sg_ingest import run_data_gov_sg_collections_ingest_task
        run_data_gov_sg_collections_ingest_task.delay()
    else:
        logger.info("data_gov_sg_collection already has data, skipping bootstrap ingest")


@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup."""
    init_db()
    print("Database initialized")
    _bootstrap_data_gov_sg_ingest()


# Exception handlers for Problem JSON responses
app.add_exception_handler(APIException, api_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(runs.router)
app.include_router(ws.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "IMDA Policy Analytics API", "status": "running"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
