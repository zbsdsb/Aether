from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.services.provider.adapters.antigravity.client import (
    fetch_available_models,
    load_code_assist,
    parse_retry_delay,
)
from src.services.provider.adapters.antigravity.constants import (
    DAILY_BASE_URL,
    PROD_BASE_URL,
    SANDBOX_BASE_URL,
)

# ---------------------------------------------------------------------------
# load_code_assist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_code_assist_falls_back_on_500() -> None:
    """500 时 fallback 到下一个 URL（Sandbox → Daily → Prod 顺序）。"""
    resp_fail = httpx.Response(500, json={"error": {"message": "boom"}})
    resp_ok = httpx.Response(200, json={"cloudaicompanionProject": "project-1"})

    client = SimpleNamespace(post=AsyncMock(side_effect=[resp_fail, resp_ok]))

    with (
        patch(
            "src.clients.http_client.HTTPClientPool.get_proxy_client",
            AsyncMock(return_value=client),
        ),
        patch(
            "src.services.provider.adapters.antigravity.client.url_availability.get_ordered_urls",
            return_value=[SANDBOX_BASE_URL, DAILY_BASE_URL, PROD_BASE_URL],
        ),
    ):
        data = await load_code_assist("tok", proxy_config=None, timeout_seconds=1.0)

    assert data["cloudaicompanionProject"] == "project-1"
    assert client.post.await_count == 2
    assert client.post.call_args_list[0].args[0] == f"{SANDBOX_BASE_URL}/v1internal:loadCodeAssist"
    assert client.post.call_args_list[1].args[0] == f"{DAILY_BASE_URL}/v1internal:loadCodeAssist"


@pytest.mark.asyncio
async def test_load_code_assist_4xx_does_not_fallback() -> None:
    """401/403 等 4xx 客户端错误不应 fallback，直接抛出。"""
    resp_401 = httpx.Response(401, json={"error": "unauthorized"}, text="unauthorized")

    client = SimpleNamespace(post=AsyncMock(return_value=resp_401))

    with (
        patch(
            "src.clients.http_client.HTTPClientPool.get_proxy_client",
            AsyncMock(return_value=client),
        ),
        patch(
            "src.services.provider.adapters.antigravity.client.url_availability.get_ordered_urls",
            return_value=[SANDBOX_BASE_URL, DAILY_BASE_URL],
        ),
        pytest.raises(RuntimeError, match="status=401"),
    ):
        await load_code_assist("tok", proxy_config=None, timeout_seconds=1.0)

    # 只调用了一次（没有 fallback 到第二个 URL）
    assert client.post.await_count == 1


@pytest.mark.asyncio
async def test_load_code_assist_requires_token() -> None:
    with pytest.raises(ValueError):
        await load_code_assist("", proxy_config=None)


# ---------------------------------------------------------------------------
# fetch_available_models
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_available_models_falls_back_on_500() -> None:
    resp_fail = httpx.Response(500, json={"error": {"message": "boom"}})
    resp_ok = httpx.Response(
        200,
        json={
            "models": {
                "claude-sonnet-4": {
                    "displayName": "Claude Sonnet 4",
                    "quotaInfo": {"remainingFraction": 0.75, "resetTime": "2024-01-15T12:00:00Z"},
                }
            }
        },
    )

    client = SimpleNamespace(post=AsyncMock(side_effect=[resp_fail, resp_ok]))

    with (
        patch(
            "src.clients.http_client.HTTPClientPool.get_proxy_client",
            AsyncMock(return_value=client),
        ),
        patch(
            "src.services.provider.adapters.antigravity.client.url_availability.get_ordered_urls",
            return_value=[DAILY_BASE_URL, PROD_BASE_URL],
        ),
    ):
        data = await fetch_available_models(
            "tok",
            project_id="project-1",
            proxy_config=None,
            timeout_seconds=1.0,
        )

    assert "models" in data
    assert client.post.await_count == 2
    assert (
        client.post.call_args_list[0].args[0] == f"{DAILY_BASE_URL}/v1internal:fetchAvailableModels"
    )
    assert (
        client.post.call_args_list[1].args[0] == f"{PROD_BASE_URL}/v1internal:fetchAvailableModels"
    )


@pytest.mark.asyncio
async def test_fetch_available_models_requires_project_id() -> None:
    with pytest.raises(ValueError):
        await fetch_available_models("tok", project_id="", proxy_config=None)


# ---------------------------------------------------------------------------
# parse_retry_delay
# ---------------------------------------------------------------------------


def test_parse_retry_delay_from_retry_info() -> None:
    error_json = '{"error": {"details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "1.5s"}]}}'
    delay = parse_retry_delay(error_json)
    assert delay is not None
    # 1500ms + 200ms buffer = 1700ms = 1.7s
    assert 1.5 < delay < 2.0


def test_parse_retry_delay_from_quota_reset() -> None:
    error_json = '{"error": {"details": [{"metadata": {"quotaResetDelay": "200ms"}}]}}'
    delay = parse_retry_delay(error_json)
    assert delay is not None
    assert 0.3 < delay < 0.5


def test_parse_retry_delay_invalid() -> None:
    assert parse_retry_delay("not json") is None
    assert parse_retry_delay("{}") is None
    assert parse_retry_delay('{"error": {}}') is None
