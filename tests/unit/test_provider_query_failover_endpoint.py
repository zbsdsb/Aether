from types import SimpleNamespace

from src.api.admin.provider_query import (
    _build_direct_test_candidates,
    _build_test_attempts_from_candidate_keys,
    _filter_test_candidates_by_endpoint,
    _resolve_test_effective_model,
)


def _build_provider() -> tuple[SimpleNamespace, SimpleNamespace, SimpleNamespace]:
    endpoint_a = SimpleNamespace(id="ep-a", api_format="openai:chat", is_active=True)
    endpoint_b = SimpleNamespace(id="ep-b", api_format="claude:cli", is_active=True)
    key_all = SimpleNamespace(
        id="key-all", is_active=True, api_formats=["openai:chat", "claude:cli"]
    )
    key_b = SimpleNamespace(id="key-b", is_active=True, api_formats=["claude:cli"])
    provider = SimpleNamespace(
        id="provider-1", endpoints=[endpoint_a, endpoint_b], api_keys=[key_all, key_b]
    )
    return provider, endpoint_a, endpoint_b


def test_build_direct_test_candidates_respects_endpoint_id() -> None:
    provider, _endpoint_a, endpoint_b = _build_provider()

    candidates = _build_direct_test_candidates(provider, endpoint_id=endpoint_b.id)  # type: ignore[arg-type]

    assert {candidate.endpoint.id for candidate in candidates} == {endpoint_b.id}
    assert {candidate.key.id for candidate in candidates} == {"key-all", "key-b"}


def test_filter_test_candidates_by_endpoint_keeps_matching_candidates() -> None:
    provider, endpoint_a, endpoint_b = _build_provider()
    candidates = _build_direct_test_candidates(provider)  # type: ignore[arg-type]

    filtered = _filter_test_candidates_by_endpoint(candidates, endpoint_a.id)

    assert {candidate.endpoint.id for candidate in filtered} == {endpoint_a.id}
    assert all(candidate.endpoint.id != endpoint_b.id for candidate in filtered)


def test_resolve_test_effective_model_prefers_pool_key_mapping() -> None:
    provider, endpoint_a, _endpoint_b = _build_provider()
    candidate = _build_direct_test_candidates(provider, endpoint_id=endpoint_a.id)[0]  # type: ignore[arg-type]
    pool_key = SimpleNamespace(id="pool-key", _pool_mapping_matched_model="mapped-model")
    request = SimpleNamespace(mode="global", model_name="gpt-4")

    effective = _resolve_test_effective_model(
        provider=provider,  # type: ignore[arg-type]
        candidate=candidate,
        request=request,  # type: ignore[arg-type]
        gm_obj=None,
        key=pool_key,
    )

    assert effective == "mapped-model"


def test_build_test_attempts_from_candidate_keys_includes_retry_index() -> None:
    candidate_keys = [
        SimpleNamespace(
            candidate_index=2,
            retry_index=1,
            key_id="key-b",
            key_name="Key B",
            auth_type="api_key",
            status="failed",
            skip_reason=None,
            error_message="timeout",
            status_code=504,
            latency_ms=1200,
        )
    ]

    attempts = _build_test_attempts_from_candidate_keys(
        candidate_keys=candidate_keys,
        candidate_meta_by_pair={
            (2, "key-b"): {
                "endpoint_api_format": "openai:chat",
                "endpoint_base_url": "https://example.test/v1",
                "effective_model": "mapped-model",
            }
        },
        candidate_meta_by_index={},
    )

    assert len(attempts) == 1
    assert attempts[0].retry_index == 1
    assert attempts[0].effective_model == "mapped-model"
    assert attempts[0].endpoint_api_format == "openai:chat"
