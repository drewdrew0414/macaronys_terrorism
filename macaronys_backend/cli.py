from __future__ import annotations

import asyncio
import sys

import uvicorn

from macaronys_backend.config import settings
from macaronys_backend.logging_config import configure_logging
from macaronys_backend.services.local_worker import run_local_ai_worker


def main() -> None:
    configure_logging()

    if len(sys.argv) > 1 and sys.argv[1] == "local-worker":
        asyncio.run(run_local_ai_worker())
        return

    if len(sys.argv) > 1 and sys.argv[1] == "discord-bot":
        from macaronys_backend.discord_bot import run_discord_bot

        asyncio.run(run_discord_bot())
        return

    uvicorn.run(
        "macaronys_backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.app_env == "development",
    )
