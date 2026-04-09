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
    provider_id: str,
    key_id: str,
    provider_priority: int,
    internal_priority: int,
    global_priority: int,
) -> ProviderCandidate:
    provider = SimpleNamespace(
        id=provider_id,
        name=f"provider-{provider_id}",
        provider_priority=provider_priority,
        keep_priority_on_conversion=False,
    )
    endpoint = SimpleNamespace(id=f"endpoint-{key_id}")
    key = SimpleNamespace(
        id=key_id,
        internal_priority=internal_priority,
        global_priority_by_format={"openai:chat": global_priority},
    )
    return ProviderCandidate(
        provider=cast(Provider, provider),
        endpoint=cast(ProviderEndpoint, endpoint),
        key=cast(ProviderAPIKey, key),
        needs_conversion=False,
        provider_api_format="openai:chat",
    )


def test_priority_sort_provider_mode_prefers_model_level_provider_and_key_override() -> None:
    db = MagicMock()
    sorter = CandidateSorter(
        SchedulingConfig(
            priority_mode=SchedulingConfig.PRIORITY_MODE_PROVIDER,
            scheduling_mode=SchedulingConfig.SCHEDULING_MODE_FIXED_ORDER,
        )
    )
    first = _make_candidate(
        provider_id="provider-a",
        key_id="key-a",
        provider_priority=1,
        internal_priority=1,
        global_priority=5,
    )
    second = _make_candidate(
        provider_id="provider-b",
        key_id="key-b",
        provider_priority=9,
        internal_priority=9,
        global_priority=1,
    )

    with (
        patch(
            "src.services.scheduling.candidate_sorter.SystemConfigService.is_keep_priority_on_conversion",
            return_value=True,
        ),
        patch(
            "src.services.scheduling.candidate_sorter.load_global_model_routing_overrides",
            return_value={
                "provider_priorities": {"provider-b": 0},
                "key_internal_priorities": {"key-b": 0},
                "key_priorities_by_format": {},
            },
        ),
    ):
        result = sorter._apply_priority_mode_sort(
            [first, second],
            db,
            affinity_key=None,
            api_format="openai:chat",
            global_model_id="gm-1",
        )

    assert [candidate.key.id for candidate in result] == ["key-b", "key-a"]


def test_priority_sort_global_key_mode_prefers_model_level_key_format_override() -> None:
    db = MagicMock()
    sorter = CandidateSorter(
        SchedulingConfig(
            priority_mode=SchedulingConfig.PRIORITY_MODE_GLOBAL_KEY,
            scheduling_mode=SchedulingConfig.SCHEDULING_MODE_FIXED_ORDER,
        )
    )
    first = _make_candidate(
        provider_id="provider-a",
        key_id="key-a",
        provider_priority=1,
        internal_priority=1,
        global_priority=1,
    )
    second = _make_candidate(
        provider_id="provider-b",
        key_id="key-b",
        provider_priority=2,
        internal_priority=2,
        global_priority=9,
    )

    with (
        patch(
            "src.services.scheduling.candidate_sorter.SystemConfigService.is_keep_priority_on_conversion",
            return_value=True,
        ),
        patch(
            "src.services.scheduling.candidate_sorter.load_global_model_routing_overrides",
            return_value={
                "provider_priorities": {},
                "key_internal_priorities": {},
                "key_priorities_by_format": {"key-b": {"openai:chat": 0}},
            },
        ),
    ):
        result = sorter._apply_priority_mode_sort(
            [first, second],
            db,
            affinity_key=None,
            api_format="openai:chat",
            global_model_id="gm-1",
        )

    assert [candidate.key.id for candidate in result] == ["key-b", "key-a"]


def test_load_balance_groups_use_model_level_overrides() -> None:
    db = MagicMock()
    sorter = CandidateSorter(
        SchedulingConfig(
            priority_mode=SchedulingConfig.PRIORITY_MODE_PROVIDER,
            scheduling_mode=SchedulingConfig.SCHEDULING_MODE_LOAD_BALANCE,
        )
    )
    first = _make_candidate(
        provider_id="provider-a",
        key_id="key-a",
        provider_priority=1,
        internal_priority=1,
        global_priority=1,
    )
    second = _make_candidate(
        provider_id="provider-b",
        key_id="key-b",
        provider_priority=8,
        internal_priority=8,
        global_priority=8,
    )

    with patch(
        "src.services.scheduling.candidate_sorter.load_global_model_routing_overrides",
        return_value={
            "provider_priorities": {"provider-b": 0},
            "key_internal_priorities": {"key-b": 0},
            "key_priorities_by_format": {},
        },
    ):
        result = sorter._apply_load_balance(
            [first, second],
            db=db,
            api_format="openai:chat",
            global_model_id="gm-1",
        )

    assert [candidate.key.id for candidate in result] == ["key-b", "key-a"]
