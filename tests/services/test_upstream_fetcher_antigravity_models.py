from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.services.model.upstream_fetcher import UpstreamModelsFetchContext, fetch_models_for_key


@pytest.mark.asyncio
async def test_fetch_models_for_key_antigravity_parses_quota() -> None:
    mock_resp = {
        "models": {
            "claude-sonnet-4": {
                "displayName": "Claude Sonnet 4",
                "quotaInfo": {"remainingFraction": 0.75, "resetTime": "2024-01-15T12:00:00Z"},
            },
            "gemini-2.5-pro": {
                "displayName": "Gemini 2.5 Pro",
                "quotaInfo": {"remainingFraction": 0.0},
            },
        }
    }

    ctx = UpstreamModelsFetchContext(
        provider_type="antigravity",
        api_key_value="tok",
        format_to_endpoint={},
        proxy_config=None,
        auth_config={"project_id": "project-1"},
    )

    with patch(
        "src.services.provider.adapters.antigravity.client.fetch_available_models",
        AsyncMock(return_value=mock_resp),
    ):
        models, errors, ok, meta = await fetch_models_for_key(ctx, timeout_seconds=1.0)

    assert ok is True
    assert errors == []

    ids = {m.get("id") for m in models}
    assert "claude-sonnet-4" in ids
    assert "gemini-2.5-pro" in ids

    assert isinstance(meta, dict)
    quota = meta["antigravity"]["quota_by_model"]
    assert quota["claude-sonnet-4"]["remaining_fraction"] == 0.75
    assert quota["claude-sonnet-4"]["used_percent"] == 25.0
    assert quota["claude-sonnet-4"]["reset_time"] == "2024-01-15T12:00:00Z"
    assert quota["gemini-2.5-pro"]["used_percent"] == 100.0


@pytest.mark.asyncio
async def test_fetch_models_for_key_antigravity_requires_project_id() -> None:
    ctx = UpstreamModelsFetchContext(
        provider_type="antigravity",
        api_key_value="tok",
        format_to_endpoint={},
        proxy_config=None,
        auth_config={},
    )

    models, errors, ok, meta = await fetch_models_for_key(ctx, timeout_seconds=1.0)

    assert ok is False
    assert models == []
    assert meta is None
    assert any("project_id" in e for e in errors)
