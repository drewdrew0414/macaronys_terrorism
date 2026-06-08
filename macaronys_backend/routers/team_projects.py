from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from macaronys_backend.dependencies import get_session
from macaronys_backend.schemas.team_project import (
    PeerReviewCreate,
    PeerReviewRead,
    PeerReviewSummary,
    TeamProjectComplete,
    TeamProjectCreate,
    TeamProjectMemberJoin,
    TeamProjectMemberRead,
    TeamProjectRead,
)
from macaronys_backend.services.team_project_service import (
    complete_team_project,
    create_team_project,
    join_team_project,
    list_project_review_summary,
    list_team_project_members,
    list_team_projects,
    submit_peer_review,
)

router = APIRouter(prefix="/api/team-projects", tags=["team-projects"])


@router.post("", response_model=TeamProjectRead, status_code=201)
async def create_team_project_route(
    payload: TeamProjectCreate,
    session: AsyncSession = Depends(get_session),
) -> TeamProjectRead:
    return await create_team_project(session, payload)


@router.get("", response_model=list[TeamProjectRead])
async def list_team_projects_route(
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[TeamProjectRead]:
    return await list_team_projects(session, status_filter=status)


@router.get("/{project_id}/members", response_model=list[TeamProjectMemberRead])
async def list_team_project_members_route(
    project_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[TeamProjectMemberRead]:
    members = await list_team_project_members(session, project_id)
    return [TeamProjectMemberRead.model_validate(member) for member in members]


@router.post("/{project_id}/join", response_model=TeamProjectMemberRead)
async def join_team_project_route(
    project_id: str,
    payload: TeamProjectMemberJoin,
    session: AsyncSession = Depends(get_session),
) -> TeamProjectMemberRead:
    member = await join_team_project(
        session,
        project_id=project_id,
        user_id=payload.user_id,
        role=payload.role,
    )
    return TeamProjectMemberRead.model_validate(member)


@router.post("/{project_id}/complete", response_model=TeamProjectRead)
async def complete_team_project_route(
    project_id: str,
    payload: TeamProjectComplete,
    session: AsyncSession = Depends(get_session),
) -> TeamProjectRead:
    return await complete_team_project(session, project_id, payload.actor_id)


@router.post("/{project_id}/reviews", response_model=PeerReviewRead, status_code=201)
async def submit_peer_review_route(
    project_id: str,
    payload: PeerReviewCreate,
    session: AsyncSession = Depends(get_session),
) -> PeerReviewRead:
    return await submit_peer_review(session, project_id, payload)


@router.get("/{project_id}/reviews/summary", response_model=list[PeerReviewSummary])
async def list_project_review_summary_route(
    project_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[PeerReviewSummary]:
    return await list_project_review_summary(session, project_id)
