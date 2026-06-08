from __future__ import annotations

from datetime import datetime, timezone

from macaronys_backend.models import PeerReview
from macaronys_backend.services.team_project_service import peer_review_to_read


def test_peer_review_response_does_not_expose_writer_id() -> None:
    review = PeerReview(
        id="review-1",
        project_id="project-1",
        target_id="target-user",
        writer_id="writer-user",
        rating=5,
        reason="역할을 성실히 수행함",
        position="자료조사",
        created_at=datetime(2026, 6, 7, tzinfo=timezone.utc),
    )

    payload = peer_review_to_read(review).model_dump()

    assert payload["target_id"] == "target-user"
    assert payload["rating"] == 5
    assert "writer_id" not in payload
