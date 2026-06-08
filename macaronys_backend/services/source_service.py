from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from macaronys_backend.enums import JobStatus, SourceStatus, SourceType
from macaronys_backend.models import AiJob, AssignmentCandidate, Source
from macaronys_backend.services.prompt_builder import build_assignment_extraction_prompt
from macaronys_backend.utils.time import utc_now


async def create_source_and_ai_job(
    session: AsyncSession,
    source_type: SourceType,
    title: str,
    raw_text: str,
    storage_path: str | None = None,
    mime_type: str | None = None,
    file_size: int | None = None,
    claimed_by: str | None = None,
) -> tuple[Source, AiJob]:
    """자료 레코드와 추출용 AI 잡을 함께 생성한다.

    claimed_by 를 주면 잡을 곧바로 running 상태로 잠가, 외부(로컬/서버) 워커가
    가져가지 않도록 한다. Discord 봇의 자체 순차 처리 큐가 직접 처리할 때 사용한다.
    """
    source = Source(
        source_type=source_type.value,
        title=title,
        storage_path=storage_path,
        mime_type=mime_type,
        file_size=file_size,
        raw_text=raw_text,
        status=SourceStatus.processing.value,
    )
    session.add(source)
    await session.flush()

    now = utc_now()
    job = AiJob(
        source_id=source.id,
        job_type="extract_assignments",
        status=JobStatus.running.value if claimed_by else JobStatus.queued.value,
        prompt=build_assignment_extraction_prompt(raw_text),
        locked_by=claimed_by,
        locked_at=now if claimed_by else None,
        started_at=now if claimed_by else None,
    )
    session.add(job)
    await session.commit()
    await session.refresh(source)
    await session.refresh(job)
    return source, job


async def get_source(session: AsyncSession, source_id: str) -> Source:
    source = await session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


async def list_candidates(
    session: AsyncSession,
    source_id: str,
) -> list[AssignmentCandidate]:
    rows = await session.execute(
        select(AssignmentCandidate)
        .where(AssignmentCandidate.source_id == source_id)
        .order_by(AssignmentCandidate.created_at.asc())
    )
    return list(rows.scalars().all())
