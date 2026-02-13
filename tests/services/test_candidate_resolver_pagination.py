from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.services.cache.aware_scheduler import CacheAwareScheduler
from src.services.orchestration.candidate_resolver import CandidateResolver


class _FakeScheduler:
    def __init__(self) -> None:
        self.calls: list[int] = []
        self.scheduling_mode = CacheAwareScheduler.SCHEDULING_MODE_FIXED_ORDER
        self.priority_mode = CacheAwareScheduler.PRIORITY_MODE_PROVIDER

    async def list_all_candidates(
        self,
        *,
        db: Any,
        api_format: str,
        model_name: str,
        affinity_key: str | None = None,
        user_api_key: Any | None = None,
        provider_offset: int = 0,
        provider_limit: int | None = None,
        max_candidates: int | None = None,
        is_stream: bool = False,
        capability_requirements: dict[str, bool] | None = None,
    ) -> tuple[list[Any], str, int]:
        _ = (
            db,
            api_format,
            model_name,
            affinity_key,
            user_api_key,
            max_candidates,
            is_stream,
            capability_requirements,
        )
        assert provider_limit is not None

        self.calls.append(int(provider_offset))

        if provider_offset == 0:
            # Simulate a provider page that has providers but no eligible candidates.
            return [], "gm1", int(provider_limit)

        if provider_offset == int(provider_limit):
            # Next page yields one eligible candidate and is also the last provider page.
            cand = SimpleNamespace(
                provider=SimpleNamespace(id="p1", name="prov"),
                endpoint=SimpleNamespace(id="e1"),
                key=SimpleNamespace(id="k1"),
                is_skipped=False,
                skip_reason=None,
                is_cached=False,
                needs_conversion=False,
                provider_api_format=str(api_format),
                mapping_matched_model=None,
            )
            return [cand], "gm1", 5

        return [], "gm1", 0

    async def reorder_candidates(
        self,
        candidates: list[Any],
        db: Any = None,
        affinity_key: str | None = None,
        api_format: str | None = None,
        global_model_id: str | None = None,
    ) -> list[Any]:
        return candidates


@pytest.mark.asyncio
async def test_candidate_resolver_pagination_continues_on_empty_candidate_batch() -> None:
    db = MagicMock()
    scheduler = _FakeScheduler()
    resolver = CandidateResolver(db=db, cache_scheduler=scheduler)  # type: ignore[arg-type]

    candidates, global_model_id = await resolver.fetch_candidates(
        api_format="openai:chat",
        model_name="gpt-4o",
        affinity_key="a1",
        user_api_key=None,
        request_id="r1",
        is_stream=False,
        capability_requirements=None,
    )

    assert global_model_id == "gm1"
    assert len(candidates) == 1
    assert scheduler.calls == [0, 20]
