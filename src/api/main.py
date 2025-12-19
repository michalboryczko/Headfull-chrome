"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.utils.logging import AccessLogMiddleware, get_logger, setup_logging

# Setup logging first
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup/shutdown events."""
    logger.info("Starting Headfull Chrome API", version="0.1.0")

    # Import here to avoid circular imports
    from src.browser.manager import browser_manager
    from src.jobs.queue import job_queue

    # Initialize browser manager
    await browser_manager.initialize()
    logger.info("Browser manager initialized")

    # Initialize job queue
    await job_queue.start()
    logger.info("Job queue started")

    yield

    # Cleanup
    logger.info("Shutting down...")
    await job_queue.stop()
    await browser_manager.cleanup()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Headfull Chrome API",
    description="Browser automation API with real display via Xvfb",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add access logging middleware
app.add_middleware(AccessLogMiddleware)

# Include API routes
app.include_router(router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
