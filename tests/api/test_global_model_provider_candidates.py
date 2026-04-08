from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from src.api.admin.models.global_models import (
    _build_provider_candidate_item,
    _build_provider_candidates_payload,
    _match_global_model_against_cached_models,
)


def _provider(
    *,
    provider_id: str,
    name: str,
    website: str = "https://provider.example.com",
    is_active: bool = True,
) -> Any:
    return SimpleNamespace(
        id=provider_id,
        name=name,
        website=website,
        is_active=is_active,
    )


def _global_model(
    *,
    model_id: str = "gm-1",
    name: str = "gpt-5.4",
    config: dict[str, Any] | None = None,
) -> Any:
    return SimpleNamespace(
        id=model_id,
        name=name,
        config=config or {},
    )


def test_match_global_model_against_cached_models_supports_exact_and_regex() -> None:
    global_model = _global_model(
        name="gpt-5.4",
        config={"model_mappings": [r"^gpt-5\.4($|-)", r"^gpt-5(\.|$)"]},
    )

    matched, models = _match_global_model_against_cached_models(
        global_model,
        [
            {"id": "gpt-5.4"},
            {"id": "gpt-5.4-mini"},
            {"id": "claude-sonnet-4.5"},
        ],
    )

    assert matched is True
    assert [item["id"] for item in models] == ["gpt-5.4", "gpt-5.4-mini"]


def test_build_provider_candidate_item_marks_unknown_without_cached_models() -> None:
    candidate = _build_provider_candidate_item(
        provider=_provider(provider_id="provider-1", name="Provider One"),
        global_model=_global_model(),
        linked_provider_ids=set(),
        cached_models=None,
    )

    assert candidate.provider_id == "provider-1"
    assert candidate.match_status == "unknown"
    assert candidate.already_linked is False
    assert candidate.cached_models == []
    assert candidate.cached_model_count == 0


def test_build_provider_candidate_item_marks_matched_and_already_linked() -> None:
    candidate = _build_provider_candidate_item(
        provider=_provider(provider_id="provider-1", name="Provider One"),
        global_model=_global_model(),
        linked_provider_ids={"provider-1"},
        cached_models=[{"id": "gpt-5.4"}, {"id": "gpt-4.1"}],
    )

    assert candidate.already_linked is True
    assert candidate.match_status == "matched"
    assert [item["id"] for item in candidate.cached_models] == ["gpt-5.4", "gpt-4.1"]


def test_build_provider_candidate_item_marks_not_matched_when_cache_exists() -> None:
    candidate = _build_provider_candidate_item(
        provider=_provider(provider_id="provider-2", name="Provider Two"),
        global_model=_global_model(),
        linked_provider_ids=set(),
        cached_models=[{"id": "claude-sonnet-4.5"}],
    )

    assert candidate.match_status == "not_matched"
    assert candidate.cached_model_count == 1


def test_build_provider_candidates_payload_sorts_by_match_status_then_linked_then_name() -> None:
    payload = _build_provider_candidates_payload(
        providers=[
            _provider(provider_id="provider-c", name="Gamma"),
            _provider(provider_id="provider-a", name="Alpha"),
            _provider(provider_id="provider-b", name="Beta"),
        ],
        global_model=_global_model(),
        linked_provider_ids={"provider-b"},
        provider_cached_models={
            "provider-a": [{"id": "gpt-5.4"}],
            "provider-b": None,
            "provider-c": [{"id": "claude-sonnet-4.5"}],
        },
    )

    assert [item.provider_id for item in payload] == [
        "provider-a",  # matched
        "provider-c",  # not_matched
        "provider-b",  # unknown but already linked
    ]
