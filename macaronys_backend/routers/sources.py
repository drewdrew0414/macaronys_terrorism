from __future__ import annotations

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from macaronys_backend.config import settings
from macaronys_backend.dependencies import get_session
from macaronys_backend.enums import SourceType
from macaronys_backend.schemas.ai import AiJobRead
from macaronys_backend.schemas.source import (
    CandidateRead,
    IngestResponse,
    SourceChatCreate,
    SourceRead,
    SourceTextCreate,
)
from macaronys_backend.services.document_parser import (
    detect_source_type,
    extract_text_from_file,
)
from macaronys_backend.services.file_storage import save_upload_file
from macaronys_backend.services.source_service import (
    create_source_and_ai_job,
    get_source,
    list_candidates,
)

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.post("/chat", response_model=IngestResponse, status_code=202)
async def ingest_chat_source(
    payload: SourceChatCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> IngestResponse:
    source, job = await create_source_and_ai_job(
        session=session,
        source_type=SourceType.chat,
        title=payload.title,
        raw_text=payload.raw_text,
    )
    await _enqueue_if_server_mode(request, job.id)
    return IngestResponse(
        source=SourceRead.model_validate(source),
        ai_job=AiJobRead.model_validate(job),
    )


@router.post("/text", response_model=IngestResponse, status_code=202)
async def ingest_text_source(
    payload: SourceTextCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> IngestResponse:
    source, job = await create_source_and_ai_job(
        session=session,
        source_type=SourceType.txt,
        title=payload.title,
        raw_text=payload.raw_text,
    )
    await _enqueue_if_server_mode(request, job.id)
    return IngestResponse(
        source=SourceRead.model_validate(source),
        ai_job=AiJobRead.model_validate(job),
    )


@router.post("/upload", response_model=IngestResponse, status_code=202)
async def upload_source_file(
    request: Request,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> IngestResponse:
    path, file_size = await save_upload_file(file)
    source_type = detect_source_type(file.filename or path.name, file.content_type)
    raw_text = extract_text_from_file(path, source_type)

    source, job = await create_source_and_ai_job(
        session=session,
        source_type=source_type,
        title=file.filename or path.name,
        raw_text=raw_text,
        storage_path=str(path),
        mime_type=file.content_type,
        file_size=file_size,
    )
    await _enqueue_if_server_mode(request, job.id)
    return IngestResponse(
        source=SourceRead.model_validate(source),
        ai_job=AiJobRead.model_validate(job),
    )


@router.get("/{source_id}", response_model=SourceRead)
async def get_source_route(
    source_id: str,
    session: AsyncSession = Depends(get_session),
) -> SourceRead:
    source = await get_source(session, source_id)
    return SourceRead.model_validate(source)


@router.get("/{source_id}/candidates", response_model=list[CandidateRead])
async def list_candidates_route(
    source_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[CandidateRead]:
    candidates = await list_candidates(session, source_id)
    return [CandidateRead.model_validate(candidate) for candidate in candidates]


async def _enqueue_if_server_mode(request: Request, job_id: str) -> None:
    if settings.ai_execution_mode == "server":
        await request.app.state.ai_processor.enqueue(job_id)
