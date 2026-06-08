from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from macaronys_backend.config import settings
from macaronys_backend.dependencies import get_session
from macaronys_backend.schemas.health import HealthRead

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthRead)
async def health(session: AsyncSession = Depends(get_session)) -> HealthRead:
    try:
        await session.execute(select(1))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"database unavailable: {exc}",
        ) from exc

    return HealthRead(
        status="ok",
        app=settings.app_name,
        ai_execution_mode=settings.ai_execution_mode,
        ollama_model=settings.ollama_model,
        database="ok",
    )
