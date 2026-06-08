from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from macaronys_backend.config import settings
from macaronys_backend.dependencies import get_session, require_worker_token
from macaronys_backend.schemas.ai import AiJobRead, LocalAiJobRead, LocalAiJobResult
from macaronys_backend.services.ai_job_service import (
    claim_next_ai_job,
    get_ai_job,
    submit_ai_job_result,
)

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/jobs/{job_id}", response_model=AiJobRead)
async def get_ai_job_route(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> AiJobRead:
    job = await get_ai_job(session, job_id)
    return AiJobRead.model_validate(job)


@router.get(
    "/worker/jobs/next",
    response_model=LocalAiJobRead,
    dependencies=[Depends(require_worker_token)],
)
async def claim_next_ai_job_route(
    response: Response,
    worker_id: str = "local-worker",
    session: AsyncSession = Depends(get_session),
) -> LocalAiJobRead | Response:
    job = await claim_next_ai_job(session, worker_id)
    if job is None:
        response.status_code = status.HTTP_204_NO_CONTENT
        return response

    return LocalAiJobRead(
        id=job.id,
        source_id=job.source_id,
        job_type=job.job_type,
        model=settings.ollama_model,
        prompt=job.prompt,
    )


@router.post(
    "/jobs/{job_id}/result",
    response_model=AiJobRead,
    dependencies=[Depends(require_worker_token)],
)
async def submit_local_ai_result_route(
    job_id: str,
    payload: LocalAiJobResult,
    session: AsyncSession = Depends(get_session),
) -> AiJobRead:
    job = await submit_ai_job_result(session, job_id, payload)
    return AiJobRead.model_validate(job)
