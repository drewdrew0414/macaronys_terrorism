from __future__ import annotations

from fastapi import Header, HTTPException, status

from macaronys_backend.config import settings
from macaronys_backend.database import get_session


async def require_worker_token(
    x_worker_token: str | None = Header(default=None, alias="X-Worker-Token"),
) -> None:
    if not settings.worker_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Worker token is not configured",
        )
    if x_worker_token != settings.worker_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid worker token",
        )


__all__ = ["get_session", "require_worker_token"]
