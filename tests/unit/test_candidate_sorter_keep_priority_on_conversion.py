from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

from src.models.database import Provider, ProviderAPIKey, ProviderEndpoint
from src.services.scheduling.candidate_sorter import CandidateSorter
from src.services.scheduling.scheduling_config import SchedulingConfig
from src.services.scheduling.schemas import ProviderCandidate


def _make_candidate(
    *,
    key_id: str,
    global_priority: int,
    needs_conversion: bool,
    provider_keep_priority_on_conversion: bool,
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
        global_priority_by_format={"openai:chat": global_priority},
    )
    return ProviderCandidate(
        provider=cast(Provider, provider),
        endpoint=cast(ProviderEndpoint, endpoint),
        key=cast(ProviderAPIKey, key),
        needs_conversion=needs_conversion,
        provider_api_format="openai:chat",
    )


def test_priority_sort_global_key_does_not_demote_when_global_keep_priority_enabled() -> None:
    db = MagicMock()
    config = SchedulingConfig(
        priority_mode=SchedulingConfig.PRIORITY_MODE_GLOBAL_KEY,
        scheduling_mode=SchedulingConfig.SCHEDULING_MODE_FIXED_ORDER,
    )
    sorter = CandidateSorter(config)

    exact = _make_candidate(
        key_id="k_exact",
        global_priority=10,
        needs_conversion=False,
        provider_keep_priority_on_conversion=False,
    )
    demoted = _make_candidate(
        key_id="k_demote",
        global_priority=1,
        needs_conversion=True,
        provider_keep_priority_on_conversion=False,
    )

    # 全局 keep_priority_on_conversion=True：不做 needs_conversion 降级分组，纯按 global_priority 排序
    with patch(
        "src.services.scheduling.candidate_sorter.SystemConfigService.is_keep_priority_on_conversion",
        return_value=True,
    ):
        result = sorter._apply_priority_mode_sort([exact, demoted], db, None, "openai:chat")

    assert [c.key.id for c in result] == ["k_demote", "k_exact"]


def test_priority_sort_global_key_demotes_convertible_when_global_keep_priority_disabled() -> None:
    db = MagicMock()
    config = SchedulingConfig(
        priority_mode=SchedulingConfig.PRIORITY_MODE_GLOBAL_KEY,
        scheduling_mode=SchedulingConfig.SCHEDULING_MODE_FIXED_ORDER,
    )
    sorter = CandidateSorter(config)

    exact = _make_candidate(
        key_id="k_exact",
        global_priority=10,
        needs_conversion=False,
        provider_keep_priority_on_conversion=False,
    )
    demoted = _make_candidate(
        key_id="k_demote",
        global_priority=1,
        needs_conversion=True,
        provider_keep_priority_on_conversion=False,
    )

    # 全局 keep_priority_on_conversion=False：需要降级的 convertible 候选整体排后
    with patch(
        "src.services.scheduling.candidate_sorter.SystemConfigService.is_keep_priority_on_conversion",
        return_value=False,
    ):
        result = sorter._apply_priority_mode_sort([exact, demoted], db, None, "openai:chat")

    assert [c.key.id for c in result] == ["k_exact", "k_demote"]


def test_priority_sort_global_key_provider_keep_priority_overrides_demotion_group() -> None:
    db = MagicMock()
    config = SchedulingConfig(
        priority_mode=SchedulingConfig.PRIORITY_MODE_GLOBAL_KEY,
        scheduling_mode=SchedulingConfig.SCHEDULING_MODE_FIXED_ORDER,
    )
    sorter = CandidateSorter(config)

    exact = _make_candidate(
        key_id="k_exact",
        global_priority=10,
        needs_conversion=False,
        provider_keep_priority_on_conversion=False,
    )
    convertible_keep = _make_candidate(
        key_id="k_keep",
        global_priority=1,
        needs_conversion=True,
        provider_keep_priority_on_conversion=True,
    )
    convertible_demote = _make_candidate(
        key_id="k_demote",
        global_priority=0,
        needs_conversion=True,
        provider_keep_priority_on_conversion=False,
    )

    with patch(
        "src.services.scheduling.candidate_sorter.SystemConfigService.is_keep_priority_on_conversion",
        return_value=False,
    ):
        result = sorter._apply_priority_mode_sort(
            [exact, convertible_demote, convertible_keep],
            db,
            None,
            "openai:chat",
        )

    assert [c.key.id for c in result] == ["k_keep", "k_exact", "k_demote"]


def test_priority_sort_provider_mode_demotes_convertible_when_global_keep_priority_disabled() -> (
    None
):
    db = MagicMock()
    config = SchedulingConfig(
        priority_mode=SchedulingConfig.PRIORITY_MODE_PROVIDER,
        scheduling_mode=SchedulingConfig.SCHEDULING_MODE_FIXED_ORDER,
    )
    sorter = CandidateSorter(config)

    exact = _make_candidate(
        key_id="k_exact",
        global_priority=10,
        needs_conversion=False,
        provider_keep_priority_on_conversion=False,
    )
    demoted = _make_candidate(
        key_id="k_demote",
        global_priority=1,
        needs_conversion=True,
        provider_keep_priority_on_conversion=False,
    )

    with patch(
        "src.services.scheduling.candidate_sorter.SystemConfigService.is_keep_priority_on_conversion",
        return_value=False,
    ):
        result = sorter._apply_priority_mode_sort([demoted, exact], db, None, "openai:chat")

    assert [c.key.id for c in result] == ["k_exact", "k_demote"]


def test_priority_sort_provider_mode_does_not_demote_when_global_keep_priority_enabled() -> None:
    db = MagicMock()
    config = SchedulingConfig(
        priority_mode=SchedulingConfig.PRIORITY_MODE_PROVIDER,
        scheduling_mode=SchedulingConfig.SCHEDULING_MODE_FIXED_ORDER,
    )
    sorter = CandidateSorter(config)

    exact = _make_candidate(
        key_id="k_exact",
        global_priority=10,
        needs_conversion=False,
        provider_keep_priority_on_conversion=False,
    )
    demoted = _make_candidate(
        key_id="k_demote",
        global_priority=1,
        needs_conversion=True,
        provider_keep_priority_on_conversion=False,
    )

    with patch(
        "src.services.scheduling.candidate_sorter.SystemConfigService.is_keep_priority_on_conversion",
        return_value=True,
    ):
        result = sorter._apply_priority_mode_sort([demoted, exact], db, None, "openai:chat")

    assert [c.key.id for c in result] == ["k_demote", "k_exact"]
