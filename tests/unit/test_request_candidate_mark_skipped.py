from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from src.services.request.candidate import RequestCandidateService


def test_mark_candidate_skipped_merges_extra_data_and_sets_fields() -> None:
    candidate = SimpleNamespace(
        status="available",
        skip_reason=None,
        finished_at=None,
        status_code=None,
        concurrent_requests=None,
        extra_data={"needs_conversion": True},
    )

    query = MagicMock()
    query.filter.return_value.first.return_value = candidate

    db = MagicMock()
    db.query.return_value = query

    RequestCandidateService.mark_candidate_skipped(
        db=db,
        candidate_id="c1",
        skip_reason="并发限制",
        status_code=429,
        concurrent_requests=12,
        extra_data={"concurrency_denied": True},
    )

    assert candidate.status == "skipped"
    assert candidate.skip_reason == "并发限制"
    assert candidate.status_code == 429
    assert candidate.concurrent_requests == 12
    assert candidate.extra_data == {"needs_conversion": True, "concurrency_denied": True}
    assert candidate.finished_at is not None
    db.flush.assert_called_once()
