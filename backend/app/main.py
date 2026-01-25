"""Main FastAPI application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health
from app.core.config import settings
from app.core.database import init_db

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)


@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup."""
    init_db()
    print("✓ Database initialized")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["health"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "IMDA Policy Analytics API", "status": "running"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
