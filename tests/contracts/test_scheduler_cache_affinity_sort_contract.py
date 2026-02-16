from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.database import Provider, ProviderAPIKey, ProviderEndpoint
from src.services.scheduling.aware_scheduler import CacheAwareScheduler, ProviderCandidate


def _make_candidate(
    *,
    key_id: str,
    global_priority: int,
    needs_conversion: bool,
    provider_keep_priority_on_conversion: bool,
    is_skipped: bool = False,
) -> ProviderCandidate:
    provider = SimpleNamespace(
        id=f"p_{key_id}",
        name=f"prov_{key_id}",
        provider_priority=1,
        keep_priority_on_conversion=provider_keep_priority_on_conversion,
    )
    endpoint = SimpleNamespace(id=f"e_{key_id}")
    key = SimpleNamespace(
        id=key_id,
        internal_priority=1,
        api_key="sk-test-1234567890",
        global_priority_by_format={"openai:chat": global_priority},
    )

    return ProviderCandidate(
        provider=cast(Provider, provider),
        endpoint=cast(ProviderEndpoint, endpoint),
        key=cast(ProviderAPIKey, key),
        is_cached=False,
        is_skipped=is_skipped,
        skip_reason="unhealthy" if is_skipped else None,
        needs_conversion=needs_conversion,
        provider_api_format="openai:chat",
    )


@pytest.mark.asyncio
async def test_cache_affinity_hit_healthy_candidate_is_always_promoted_to_front() -> None:
    """契约：缓存亲和性命中且候选健康时，无条件置顶（覆盖降级分组/优先级）。"""

    scheduler = CacheAwareScheduler()
    scheduler.scheduling_mode = CacheAwareScheduler.SCHEDULING_MODE_CACHE_AFFINITY
    scheduler.priority_mode = CacheAwareScheduler.PRIORITY_MODE_GLOBAL_KEY

    db = MagicMock()

    keep_1 = _make_candidate(
        key_id="k_keep_1",
        global_priority=1,
        needs_conversion=False,
        provider_keep_priority_on_conversion=False,
    )
    keep_2 = _make_candidate(
        key_id="k_keep_2",
        global_priority=2,
        needs_conversion=False,
        provider_keep_priority_on_conversion=False,
    )
    matched_demote = _make_candidate(
        key_id="k_cached",
        global_priority=0,
        needs_conversion=True,
        provider_keep_priority_on_conversion=False,
    )

    affinity = SimpleNamespace(
        provider_id=matched_demote.provider.id,
        endpoint_id=matched_demote.endpoint.id,
        key_id=matched_demote.key.id,
        request_count=7,
    )

    scheduler._affinity_manager = SimpleNamespace(get_affinity=AsyncMock(return_value=affinity))

    with patch(
        "src.services.system.config.SystemConfigService.is_keep_priority_on_conversion",
        return_value=False,
    ):
        result = await scheduler.reorder_candidates(
            candidates=[keep_1, matched_demote, keep_2],
            db=db,
            affinity_key="a1",
            api_format="openai:chat",
            global_model_id="gm1",
        )

    assert [c.key.id for c in result] == ["k_cached", "k_keep_1", "k_keep_2"]
    assert result[0] is matched_demote
    assert result[0].is_cached is True
    assert all(not c.is_cached for c in result[1:])


@pytest.mark.asyncio
async def test_cache_affinity_hit_skipped_candidate_is_promoted_within_its_group() -> None:
    """契约：缓存亲和性命中但候选被跳过时，只提升到其所属类别内最前面。"""

    scheduler = CacheAwareScheduler()
    scheduler.scheduling_mode = CacheAwareScheduler.SCHEDULING_MODE_CACHE_AFFINITY
    scheduler.priority_mode = CacheAwareScheduler.PRIORITY_MODE_GLOBAL_KEY

    db = MagicMock()

    keep_1 = _make_candidate(
        key_id="k_keep_1",
        global_priority=1,
        needs_conversion=False,
        provider_keep_priority_on_conversion=False,
    )
    keep_2 = _make_candidate(
        key_id="k_keep_2",
        global_priority=2,
        needs_conversion=False,
        provider_keep_priority_on_conversion=False,
    )

    demote_other = _make_candidate(
        key_id="k_demote_other",
        global_priority=0,
        needs_conversion=True,
        provider_keep_priority_on_conversion=False,
    )
    matched_demote_skipped = _make_candidate(
        key_id="k_cached",
        global_priority=10,
        needs_conversion=True,
        provider_keep_priority_on_conversion=False,
        is_skipped=True,
    )

    affinity = SimpleNamespace(
        provider_id=matched_demote_skipped.provider.id,
        endpoint_id=matched_demote_skipped.endpoint.id,
        key_id=matched_demote_skipped.key.id,
        request_count=3,
    )

    scheduler._affinity_manager = SimpleNamespace(get_affinity=AsyncMock(return_value=affinity))

    with patch(
        "src.services.system.config.SystemConfigService.is_keep_priority_on_conversion",
        return_value=False,
    ):
        result = await scheduler.reorder_candidates(
            candidates=[keep_1, demote_other, keep_2, matched_demote_skipped],
            db=db,
            affinity_key="a1",
            api_format="openai:chat",
            global_model_id="gm1",
        )

    # keep 组（exact）整体在前；matched 在 demote 组内置顶（即使 global_priority 更差）
    assert [c.key.id for c in result] == [
        "k_keep_1",
        "k_keep_2",
        "k_cached",
        "k_demote_other",
    ]
    assert result[2] is matched_demote_skipped
    assert result[2].is_cached is True
    assert all(not c.is_cached for i, c in enumerate(result) if i != 2)
