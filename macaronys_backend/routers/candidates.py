from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from macaronys_backend.dependencies import get_session
from macaronys_backend.schemas.assignment import AssignmentRead
from macaronys_backend.schemas.source import CandidateRead
from macaronys_backend.services.assignment_service import (
    accept_candidate,
    assignment_to_read,
    reject_candidate,
)
from macaronys_backend.services.notification_service import rebuild_notifications_for_assignment

router = APIRouter(prefix="/api/candidates", tags=["candidates"])


@router.post("/{candidate_id}/accept", response_model=AssignmentRead)
async def accept_candidate_route(
    candidate_id: str,
    session: AsyncSession = Depends(get_session),
) -> AssignmentRead:
    assignment = await accept_candidate(session, candidate_id)
    await rebuild_notifications_for_assignment(session, assignment)
    await session.commit()
    await session.refresh(assignment)
    return assignment_to_read(assignment)


@router.post("/{candidate_id}/reject", response_model=CandidateRead)
async def reject_candidate_route(
    candidate_id: str,
    session: AsyncSession = Depends(get_session),
) -> CandidateRead:
    return await reject_candidate(session, candidate_id)
