from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from macaronys_backend.enums import TeamMemberStatus, TeamProjectStatus
from macaronys_backend.models import (
    Assignment,
    PeerReview,
    SchoolClass,
    TeamProject,
    TeamProjectMember,
    User,
)
from macaronys_backend.schemas.team_project import (
    PeerReviewCreate,
    PeerReviewRead,
    PeerReviewSummary,
    TeamProjectCreate,
    TeamProjectRead,
)
from macaronys_backend.services.user_service import get_user
from macaronys_backend.utils.time import utc_now


async def create_team_project(
    session: AsyncSession,
    payload: TeamProjectCreate,
) -> TeamProjectRead:
    await get_user(session, payload.maker_id)
    if payload.assignment_id is not None and await session.get(Assignment, payload.assignment_id) is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if payload.class_id is not None and await session.get(SchoolClass, payload.class_id) is None:
        raise HTTPException(status_code=404, detail="Class not found")

    project = TeamProject(
        maker_id=payload.maker_id,
        assignment_id=payload.assignment_id,
        class_id=payload.class_id,
        title=payload.title,
        context=payload.context,
        max_members=payload.max_members,
        status=TeamProjectStatus.recruiting.value,
    )
    session.add(project)
    await session.flush()
    session.add(
        TeamProjectMember(
            project_id=project.id,
            user_id=payload.maker_id,
            role="maker",
            status=TeamMemberStatus.joined.value,
        )
    )
    await session.commit()
    await session.refresh(project)
    return await team_project_to_read(session, project)


async def get_team_project(session: AsyncSession, project_id: str) -> TeamProject:
    project = await session.get(TeamProject, project_id)
    if project is None or project.is_deleted:
        raise HTTPException(status_code=404, detail="Team project not found")
    return project


async def list_team_projects(
    session: AsyncSession,
    status_filter: str | None = None,
) -> list[TeamProjectRead]:
    query = (
        select(TeamProject)
        .where(TeamProject.is_deleted.is_(False))
        .order_by(TeamProject.created_at.desc())
    )
    if status_filter:
        query = query.where(TeamProject.status == status_filter)
    rows = await session.execute(query)
    return [
        await team_project_to_read(session, project)
        for project in rows.scalars().all()
    ]


async def team_project_to_read(
    session: AsyncSession,
    project: TeamProject,
) -> TeamProjectRead:
    current_count = await count_joined_members(session, project.id)
    return TeamProjectRead(
        id=project.id,
        maker_id=project.maker_id,
        assignment_id=project.assignment_id,
        class_id=project.class_id,
        title=project.title,
        context=project.context,
        max_members=project.max_members,
        current_member_count=current_count,
        status=project.status,
        is_deleted=project.is_deleted,
        created_at=project.created_at,
        updated_at=project.updated_at,
        ended_at=project.ended_at,
    )


async def count_joined_members(session: AsyncSession, project_id: str) -> int:
    row = await session.execute(
        select(func.count())
        .select_from(TeamProjectMember)
        .where(TeamProjectMember.project_id == project_id)
        .where(TeamProjectMember.status == TeamMemberStatus.joined.value)
    )
    return int(row.scalar_one())


async def list_team_project_members(
    session: AsyncSession,
    project_id: str,
) -> list[TeamProjectMember]:
    await get_team_project(session, project_id)
    rows = await session.execute(
        select(TeamProjectMember)
        .where(TeamProjectMember.project_id == project_id)
        .order_by(TeamProjectMember.joined_at.asc())
    )
    return list(rows.scalars().all())


async def join_team_project(
    session: AsyncSession,
    project_id: str,
    user_id: str,
    role: str | None = None,
) -> TeamProjectMember:
    project = await get_team_project(session, project_id)
    await get_user(session, user_id)

    if project.status != TeamProjectStatus.recruiting.value:
        raise HTTPException(status_code=409, detail="Team project is not recruiting")

    existing = await session.execute(
        select(TeamProjectMember)
        .where(TeamProjectMember.project_id == project.id)
        .where(TeamProjectMember.user_id == user_id)
    )
    member = existing.scalar_one_or_none()
    if member is not None and member.status == TeamMemberStatus.joined.value:
        raise HTTPException(status_code=409, detail="User already joined this project")

    current_count = await count_joined_members(session, project.id)
    if current_count >= project.max_members:
        raise HTTPException(status_code=409, detail="Team project is full")

    if member is None:
        member = TeamProjectMember(
            project_id=project.id,
            user_id=user_id,
            role=role,
            status=TeamMemberStatus.joined.value,
        )
        session.add(member)
    else:
        member.status = TeamMemberStatus.joined.value
        member.role = role
        member.joined_at = utc_now()

    await session.commit()
    await session.refresh(member)
    return member


async def complete_team_project(
    session: AsyncSession,
    project_id: str,
    actor_id: str,
) -> TeamProjectRead:
    project = await get_team_project(session, project_id)
    if project.maker_id != actor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the project maker can complete this project",
        )

    project.status = TeamProjectStatus.completed.value
    project.ended_at = utc_now()
    await session.commit()
    await session.refresh(project)
    return await team_project_to_read(session, project)


async def submit_peer_review(
    session: AsyncSession,
    project_id: str,
    payload: PeerReviewCreate,
) -> PeerReviewRead:
    project = await get_team_project(session, project_id)
    if project.status != TeamProjectStatus.completed.value:
        raise HTTPException(
            status_code=409,
            detail="Reviews are only allowed after the project is completed",
        )
    if payload.writer_id == payload.target_id:
        raise HTTPException(status_code=422, detail="Self review is not allowed")

    await ensure_active_member(session, project_id, payload.writer_id, "Writer")
    await ensure_active_member(session, project_id, payload.target_id, "Target")

    review = PeerReview(
        project_id=project_id,
        target_id=payload.target_id,
        writer_id=payload.writer_id,
        rating=payload.rating,
        reason=payload.reason,
        position=payload.position,
    )
    session.add(review)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Review already exists for this target in this project",
        ) from exc
    await session.refresh(review)
    return peer_review_to_read(review)


async def ensure_active_member(
    session: AsyncSession,
    project_id: str,
    user_id: str,
    label: str,
) -> TeamProjectMember:
    member = await session.execute(
        select(TeamProjectMember)
        .where(TeamProjectMember.project_id == project_id)
        .where(TeamProjectMember.user_id == user_id)
        .where(TeamProjectMember.status == TeamMemberStatus.joined.value)
    )
    result = member.scalar_one_or_none()
    if result is None:
        raise HTTPException(
            status_code=422,
            detail=f"{label} is not an active member of this project",
        )
    return result


def peer_review_to_read(review: PeerReview) -> PeerReviewRead:
    return PeerReviewRead(
        id=review.id,
        project_id=review.project_id,
        target_id=review.target_id,
        rating=review.rating,
        reason=review.reason,
        position=review.position,
        created_at=review.created_at,
    )


async def list_project_review_summary(
    session: AsyncSession,
    project_id: str,
) -> list[PeerReviewSummary]:
    await get_team_project(session, project_id)
    rows = await session.execute(
        select(
            PeerReview.target_id,
            User.name,
            func.count(PeerReview.id),
            func.avg(PeerReview.rating),
        )
        .join(User, User.id == PeerReview.target_id)
        .where(PeerReview.project_id == project_id)
        .group_by(PeerReview.target_id, User.name)
        .order_by(User.name.asc())
    )
    return [
        PeerReviewSummary(
            target_id=target_id,
            target_name=target_name,
            review_count=int(review_count),
            average_rating=float(average_rating),
        )
        for target_id, target_name, review_count, average_rating in rows.all()
    ]


class UserReviewSummary:
    def __init__(self, project_title: str, average_rating: float, review_count: int) -> None:
        self.project_title = project_title
        self.average_rating = average_rating
        self.review_count = review_count


async def list_user_reviews(
    session: AsyncSession,
    user_id: str,
) -> list[UserReviewSummary]:
    rows = await session.execute(
        select(
            TeamProject.title,
            func.avg(PeerReview.rating),
            func.count(PeerReview.id),
        )
        .join(TeamProject, TeamProject.id == PeerReview.project_id)
        .where(PeerReview.target_id == user_id)
        .group_by(TeamProject.id, TeamProject.title)
        .order_by(TeamProject.title.asc())
    )
    return [
        UserReviewSummary(
            project_title=title,
            average_rating=float(avg or 0),
            review_count=int(cnt),
        )
        for title, avg, cnt in rows.all()
    ]
