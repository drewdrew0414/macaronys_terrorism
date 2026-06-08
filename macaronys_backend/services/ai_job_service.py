from __future__ import annotations

from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from macaronys_backend.config import settings
from macaronys_backend.enums import JobStatus, SourceStatus
from macaronys_backend.models import AiJob, Source
from macaronys_backend.schemas.ai import LocalAiJobResult
from macaronys_backend.services.ai_result_parser import save_candidates_from_ai_result
from macaronys_backend.utils.time import utc_now


async def get_ai_job(session: AsyncSession, job_id: str) -> AiJob:
    job = await session.get(AiJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="AI job not found")
    return job


async def requeue_stale_claimed_jobs(session: AsyncSession) -> None:
    cutoff = utc_now() - timedelta(seconds=settings.worker_claim_timeout_seconds)
    await session.execute(
        update(AiJob)
        .where(AiJob.status == JobStatus.claimed.value)
        .where(AiJob.locked_at.is_not(None))
        .where(AiJob.locked_at < cutoff)
        .values(
            status=JobStatus.queued.value,
            locked_by=None,
            locked_at=None,
            error_message="requeued after local worker timeout",
        )
    )


async def claim_next_ai_job(
    session: AsyncSession,
    worker_id: str,
) -> AiJob | None:
    if settings.ai_execution_mode != "local":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Local AI workers are only enabled when AI_EXECUTION_MODE=local",
        )

    async with session.begin():
        await requeue_stale_claimed_jobs(session)
        row = await session.execute(
            select(AiJob)
            .where(AiJob.status == JobStatus.queued.value)
            .order_by(AiJob.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = row.scalars().first()
        if job is None:
            return None
        job.status = JobStatus.claimed.value
        job.locked_by = worker_id
        job.locked_at = utc_now()
        job.attempts += 1
    return job


async def submit_ai_job_result(
    session: AsyncSession,
    job_id: str,
    payload: LocalAiJobResult,
) -> AiJob:
    job = await get_ai_job(session, job_id)
    source = await session.get(Source, job.source_id)

    if payload.success:
        if not payload.result_text:
            raise HTTPException(status_code=422, detail="result_text is required")

        try:
            await save_candidates_from_ai_result(
                session,
                job.source_id,
                payload.result_text,
            )
        except Exception as exc:
            await mark_ai_job_failed(session, job, source, str(exc))
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        job.status = JobStatus.completed.value
        job.result_text = payload.result_text
        job.error_message = None
        job.finished_at = utc_now()
        if source is not None:
            source.status = SourceStatus.done.value
    else:
        await mark_ai_job_failed(
            session,
            job,
            source,
            payload.error_message or "local worker failed",
            commit=False,
        )

    await session.commit()
    await session.refresh(job)
    return job


async def mark_ai_job_failed(
    session: AsyncSession,
    job: AiJob,
    source: Source | None,
    error_message: str,
    commit: bool = True,
) -> None:
    job.status = JobStatus.failed.value
    job.error_message = error_message
    job.finished_at = utc_now()
    if source is not None:
        source.status = SourceStatus.failed.value
        source.error_message = error_message
    if commit:
        await session.commit()
