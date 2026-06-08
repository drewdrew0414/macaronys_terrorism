from __future__ import annotations

from enum import Enum

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from macaronys_backend.enums import CandidateStatus
from macaronys_backend.models import Assignment, AssignmentCandidate
from macaronys_backend.schemas.assignment import (
    AssignmentCreate,
    AssignmentRead,
    AssignmentUpdate,
)
from macaronys_backend.schemas.source import CandidateRead
from macaronys_backend.utils.time import ensure_aware, remaining_text


def assignment_to_read(assignment: Assignment) -> AssignmentRead:
    seconds, text = remaining_text(assignment.due_at)
    return AssignmentRead(
        id=assignment.id,
        creator_id=assignment.creator_id,
        class_id=assignment.class_id,
        title=assignment.title,
        subject=assignment.subject,
        due_at=assignment.due_at,
        context=assignment.context,
        submit_method=assignment.submit_method,
        submit_link=assignment.submit_link,
        reference_link=assignment.reference_link,
        is_contest=assignment.is_contest,
        is_exam=assignment.is_exam,
        is_deleted=assignment.is_deleted,
        is_ended=assignment.is_ended,
        priority=assignment.priority,
        status=assignment.status,
        source_id=assignment.source_id,
        source_quote=assignment.source_quote,
        remaining_seconds=seconds,
        remaining_text=text,
        created_at=assignment.created_at,
        started_at=assignment.started_at,
        end_at=assignment.end_at,
        updated_at=assignment.updated_at,
    )


async def create_assignment(
    session: AsyncSession,
    payload: AssignmentCreate,
) -> Assignment:
    values = payload.model_dump()
    values["due_at"] = ensure_aware(payload.due_at)
    values["status"] = payload.status.value
    if payload.started_at is not None:
        values["started_at"] = ensure_aware(payload.started_at)
    else:
        values.pop("started_at")
    if payload.end_at is not None:
        values["end_at"] = ensure_aware(payload.end_at)
    assignment = Assignment(**values)
    session.add(assignment)
    await session.commit()
    await session.refresh(assignment)
    return assignment


async def list_assignments(session: AsyncSession) -> list[Assignment]:
    rows = await session.execute(select(Assignment).order_by(Assignment.due_at.asc()))
    return list(rows.scalars().all())


async def update_assignment(
    session: AsyncSession,
    assignment_id: str,
    payload: AssignmentUpdate,
) -> Assignment:
    assignment = await session.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")

    updates = payload.model_dump(exclude_unset=True)
    for field_name, value in updates.items():
        if isinstance(value, Enum):
            value = value.value
        if field_name in {"due_at", "started_at", "end_at"} and value is not None:
            value = ensure_aware(value)
        setattr(assignment, field_name, value)

    await session.commit()
    await session.refresh(assignment)
    return assignment


async def delete_assignment(session: AsyncSession, assignment_id: str) -> None:
    assignment = await session.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    await session.delete(assignment)
    await session.commit()


async def accept_candidate(
    session: AsyncSession,
    candidate_id: str,
) -> Assignment:
    candidate = await session.get(AssignmentCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.due_at is None:
        raise HTTPException(
            status_code=422,
            detail="Candidate has no due_at; edit it before accepting",
        )

    candidate.status = CandidateStatus.accepted.value
    assignment = Assignment(
        title=candidate.title,
        subject=candidate.subject,
        due_at=candidate.due_at,
        submit_method=candidate.submit_method,
        source_id=candidate.source_id,
        source_quote=candidate.source_quote,
    )
    session.add(assignment)
    await session.commit()
    await session.refresh(assignment)
    return assignment


async def reject_candidate(
    session: AsyncSession,
    candidate_id: str,
) -> CandidateRead:
    candidate = await session.get(AssignmentCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    candidate.status = CandidateStatus.rejected.value
    await session.commit()
    await session.refresh(candidate)
    return CandidateRead.model_validate(candidate)
