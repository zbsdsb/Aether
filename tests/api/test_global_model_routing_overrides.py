from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from src.api.admin.models.routing import (
    build_key_priority_snapshot,
    build_provider_priority_snapshot,
)
from src.models.database import Provider, ProviderAPIKey
from src.services.model.routing_overrides import normalize_global_model_routing_overrides


def test_build_provider_priority_snapshot_exposes_default_override_and_effective() -> None:
    provider = cast(
        Provider,
        SimpleNamespace(
            id="provider-1",
            provider_priority=7,
        ),
    )
    overrides = normalize_global_model_routing_overrides(
        {
            "routing_overrides": {
                "provider_priorities": {"provider-1": 2},
            }
        }
    )

    snapshot = build_provider_priority_snapshot(provider, overrides)

    assert snapshot == {
        "provider_priority": 7,
        "override_provider_priority": 2,
        "effective_provider_priority": 2,
    }


def test_build_key_priority_snapshot_exposes_provider_and_global_key_override_fields() -> None:
    key = cast(
        ProviderAPIKey,
        SimpleNamespace(
            id="key-1",
            internal_priority=9,
            global_priority_by_format={"openai:chat": 5},
        ),
    )
    overrides = normalize_global_model_routing_overrides(
        {
            "routing_overrides": {
                "key_internal_priorities": {"key-1": 3},
                "key_priorities_by_format": {"key-1": {"openai:chat": 1}},
            }
        }
    )

    snapshot = build_key_priority_snapshot(key, "openai:chat", overrides)

    assert snapshot == {
        "internal_priority": 9,
        "override_internal_priority": 3,
        "effective_internal_priority": 3,
        "default_global_priority": 5,
        "override_global_priority": 1,
        "effective_global_priority": 1,
    }
