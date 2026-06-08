from __future__ import annotations

import pytest
from fastapi import HTTPException, status

from macaronys_backend.config import settings
from macaronys_backend.dependencies import require_worker_token


@pytest.mark.asyncio
async def test_worker_token_must_be_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "worker_token", "")

    with pytest.raises(HTTPException) as exc_info:
        await require_worker_token("anything")

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.mark.asyncio
async def test_worker_token_rejects_missing_or_wrong_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "worker_token", "expected-token")

    with pytest.raises(HTTPException) as exc_info:
        await require_worker_token(None)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    with pytest.raises(HTTPException) as exc_info:
        await require_worker_token("wrong-token")

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_worker_token_accepts_matching_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "worker_token", "expected-token")

    assert await require_worker_token("expected-token") is None

