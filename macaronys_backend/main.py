from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from macaronys_backend import __version__
from macaronys_backend.config import settings
from macaronys_backend.database import SessionLocal, close_db, init_db
from macaronys_backend.logging_config import configure_logging, logger
from macaronys_backend.routers import (
    ai_jobs,
    assignments,
    candidates,
    health,
    notifications,
    sources,
    team_projects,
    users,
)
from macaronys_backend.services.ollama_client import OllamaGemmaClient
from macaronys_backend.services.server_ai_processor import ServerParallelAIProcessor


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()

    if settings.auto_create_tables:
        await init_db()

    ollama_client = OllamaGemmaClient(settings)
    ai_processor = ServerParallelAIProcessor(
        SessionLocal,
        ollama_client,
        worker_count=settings.ai_worker_concurrency,
    )
    app.state.ai_processor = ai_processor

    if settings.ai_execution_mode == "server" and settings.server_ollama_enabled:
        await ai_processor.start()
    elif settings.ai_execution_mode == "server":
        logger.info("Server AI mode is configured, but SERVER_OLLAMA_ENABLED=false; AI jobs stay queued")
    else:
        logger.info("AI execution mode is local; server will wait for local workers")

    try:
        yield
    finally:
        await ai_processor.stop()
        await close_db()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(assignments.router)
    app.include_router(sources.router)
    app.include_router(candidates.router)
    app.include_router(ai_jobs.router)
    app.include_router(notifications.router)
    app.include_router(users.router)
    app.include_router(team_projects.router)
    return app


app = create_app()
