"""Main FastAPI application."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

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
from app.core.database import init_db

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup."""
    init_db()
    print("Database initialized")


# Exception handlers for Problem JSON responses
app.add_exception_handler(APIException, api_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# CORS middleware
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

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(runs.router)
app.include_router(ws.router)

# Import and include agent routes
from app.api.routes import agents
app.include_router(agents.router, tags=["agents"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "IMDA Policy Analytics API", "status": "running"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
