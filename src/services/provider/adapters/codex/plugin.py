"""Codex provider plugin — 统一注册入口。

将 Codex 对各通用 registry 的注册集中在一个文件中：
- Envelope (OAuth headers)
- Transport Hook (URL 构建)
- Auth Enricher (OAuth enrichment)
- Behavior Variants (格式变体)

新增 provider 时参照此文件创建对应的 plugin.py 即可。
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from src.core.logger import logger

# ---------------------------------------------------------------------------
# Transport Hook
# ---------------------------------------------------------------------------


def build_codex_url(
    endpoint: Any,
    *,
    is_stream: bool,
    effective_query_params: dict[str, Any],
) -> str:
    """构建 Codex OAuth URL。

    Codex upstream (chatgpt.com/backend-api/codex) 使用 /responses
    而非标准 OpenAI 的 /v1/responses。
    """
    _ = is_stream  # Codex 不需要根据 stream 切换路径

    base = str(endpoint.base_url).rstrip("/")
    path = "/responses"
    # 如果用户已在 base_url 中包含了最终路径，不要重复
    url = base if base.endswith(path) else f"{base}{path}"
    if effective_query_params:
        query_string = urlencode(effective_query_params, doseq=True)
        if query_string:
            url = f"{url}?{query_string}"
    return url


# ---------------------------------------------------------------------------
# Auth Enricher
# ---------------------------------------------------------------------------


async def enrich_codex(
    auth_config: dict[str, Any],
    token_response: dict[str, Any],
    access_token: str,
    proxy_config: dict[str, Any] | None,
) -> dict[str, Any]:
    """Codex auth_config enrichment: parse id_token -> email/account_id/plan_type/user_id."""
    from src.core.provider_oauth_utils import parse_codex_id_token

    id_token = token_response.get("id_token")
    logger.debug(
        "Codex enrich_auth_config: id_token_present={} token_keys={}",
        bool(id_token),
        list(token_response.keys()),
    )
    codex_info = parse_codex_id_token(str(id_token) if id_token else None)
    if codex_info:
        logger.debug("Codex parsed id_token fields: {}", list(codex_info.keys()))
    if codex_info.get("email"):
        auth_config["email"] = codex_info["email"]
    if codex_info.get("account_id"):
        auth_config["account_id"] = codex_info["account_id"]
    if codex_info.get("plan_type"):
        auth_config["plan_type"] = codex_info["plan_type"]
    if codex_info.get("user_id"):
        auth_config["user_id"] = codex_info["user_id"]
    return auth_config


# ---------------------------------------------------------------------------
# Unified Registration
# ---------------------------------------------------------------------------


def register_all() -> None:
    """一次性注册 Codex 的所有 hooks 到各通用 registry。"""
    from src.core.provider_oauth_utils import register_auth_enricher
    from src.services.provider.adapters.codex.envelope import codex_oauth_envelope
    from src.services.provider.behavior import register_behavior_variant
    from src.services.provider.envelope import register_envelope
    from src.services.provider.transport import register_transport_hook

    # Envelope
    register_envelope("codex", "openai:cli", codex_oauth_envelope)
    register_envelope("codex", "", codex_oauth_envelope)

    # Transport
    register_transport_hook("codex", "openai:cli", build_codex_url)

    # Auth
    register_auth_enricher("codex", enrich_codex)

    # Behavior
    register_behavior_variant("codex", same_format=True, cross_format=True)
