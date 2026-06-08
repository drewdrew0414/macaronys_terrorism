from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from macaronys_backend.dependencies import get_session
from macaronys_backend.schemas.assignment import (
    AssignmentCreate,
    AssignmentRead,
    AssignmentUpdate,
)
from macaronys_backend.schemas.notification import RebuildNotificationsResponse
from macaronys_backend.services.assignment_service import (
    assignment_to_read,
    create_assignment,
    delete_assignment,
    list_assignments,
    update_assignment,
)
from macaronys_backend.services.notification_service import (
    rebuild_notifications_by_assignment_id,
    rebuild_notifications_for_assignment,
)

router = APIRouter(prefix="/api/assignments", tags=["assignments"])


@router.post("", response_model=AssignmentRead, status_code=201)
async def create_assignment_route(
    payload: AssignmentCreate,
    session: AsyncSession = Depends(get_session),
) -> AssignmentRead:
    assignment = await create_assignment(session, payload)
    await rebuild_notifications_for_assignment(session, assignment)
    await session.commit()
    await session.refresh(assignment)
    return assignment_to_read(assignment)


@router.get("", response_model=list[AssignmentRead])
async def list_assignments_route(
    include_expired: bool = Query(
        default=False,
        description="마감이 한 달 넘게 지난 과제까지 포함할지 여부",
    ),
    session: AsyncSession = Depends(get_session),
) -> list[AssignmentRead]:
    assignments = await list_assignments(session, include_expired=include_expired)
    return [assignment_to_read(assignment) for assignment in assignments]


@router.patch("/{assignment_id}", response_model=AssignmentRead)
async def update_assignment_route(
    assignment_id: str,
    payload: AssignmentUpdate,
    session: AsyncSession = Depends(get_session),
) -> AssignmentRead:
    assignment = await update_assignment(session, assignment_id, payload)
    await rebuild_notifications_for_assignment(session, assignment)
    await session.commit()
    await session.refresh(assignment)
    return assignment_to_read(assignment)


@router.delete("/{assignment_id}", status_code=204)
async def delete_assignment_route(
    assignment_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    await delete_assignment(session, assignment_id)
    return Response(status_code=204)


@router.post("/{assignment_id}/notifications/rebuild", response_model=RebuildNotificationsResponse)
async def rebuild_assignment_notifications_route(
    assignment_id: str,
    session: AsyncSession = Depends(get_session),
) -> RebuildNotificationsResponse:
    created_count = await rebuild_notifications_by_assignment_id(session, assignment_id)
    return RebuildNotificationsResponse(
        assignment_id=assignment_id,
        created_count=created_count,
    )
