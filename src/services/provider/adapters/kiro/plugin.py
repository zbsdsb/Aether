"""Kiro provider plugin — unified registration entry.

Kiro upstream looks like Claude CLI (Bearer token) from the outside, but uses a
custom wire protocol:
- Request: Claude Messages API -> Kiro generateAssistantResponse envelope
- Response (stream): AWS Event Stream (binary) -> Claude SSE events

This plugin registers:
- Envelope
- Transport hook (dynamic region base_url)
- Model fetcher (fixed model catalog — Kiro has no /v1/models endpoint)
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from src.services.provider.adapters.kiro.constants import (
    DEFAULT_REGION,
    KIRO_GENERATE_ASSISTANT_PATH,
)
from src.services.provider.adapters.kiro.context import get_kiro_request_context

# ---------------------------------------------------------------------------
# Fixed model catalog
# ---------------------------------------------------------------------------
# Kiro upstream has no /v1/models endpoint.  We return a static list matching
# the models accepted by map_model() in converter.py.
_KIRO_MODELS: list[dict[str, Any]] = [
    {
        "id": "claude-sonnet-4.5",
        "object": "model",
        "owned_by": "anthropic",
        "display_name": "Claude Sonnet 4.5",
    },
    {
        "id": "claude-opus-4.5",
        "object": "model",
        "owned_by": "anthropic",
        "display_name": "Claude Opus 4.5",
    },
    {
        "id": "claude-opus-4.6",
        "object": "model",
        "owned_by": "anthropic",
        "display_name": "Claude Opus 4.6",
    },
    {
        "id": "claude-haiku-4.5",
        "object": "model",
        "owned_by": "anthropic",
        "display_name": "Claude Haiku 4.5",
    },
]


async def fetch_models_kiro(
    ctx: Any,
    timeout_seconds: float,  # noqa: ARG001
) -> tuple[list[dict], list[str], bool, dict[str, Any] | None]:
    """Return a fixed model catalog for Kiro.

    Kiro upstream does not expose a ``/v1/models`` endpoint, so we skip the
    HTTP call entirely and return a hardcoded list.
    """
    _ = ctx  # not needed — no upstream call
    return list(_KIRO_MODELS), [], True, None


# ---------------------------------------------------------------------------
# Transport hook
# ---------------------------------------------------------------------------


def build_kiro_url(
    endpoint: Any,
    *,
    is_stream: bool,
    effective_query_params: dict[str, Any],
) -> str:
    """Build Kiro generateAssistantResponse URL.

    Endpoint base_url may contain a `{region}` placeholder. The actual region is
    resolved from per-request context (set by the envelope).
    """
    _ = is_stream

    base = str(getattr(endpoint, "base_url", "") or "").rstrip("/")

    ctx = get_kiro_request_context()
    region = (ctx.region if ctx else "") or DEFAULT_REGION
    if "{region}" in base:
        base = base.replace("{region}", region)

    path = KIRO_GENERATE_ASSISTANT_PATH
    url = base if base.endswith(path) else f"{base}{path}"

    if effective_query_params:
        query_string = urlencode(effective_query_params, doseq=True)
        if query_string:
            url = f"{url}?{query_string}"

    return url


# ---------------------------------------------------------------------------
# Export builder
# ---------------------------------------------------------------------------

_KIRO_SKIP_KEYS = frozenset(
    {
        "access_token",
        "expires_at",
        "updated_at",
    }
)


def kiro_export_builder(
    auth_config: dict[str, Any],
    upstream_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    """Kiro 导出：保留 auth_method / refresh_token / machine_id / profile_arn 等，
    IdC 模式额外保留 client_id / client_secret / region。"""
    data = {
        k: v
        for k, v in auth_config.items()
        if k not in _KIRO_SKIP_KEYS and v is not None and v != ""
    }
    # email 可能仅在 upstream_metadata.kiro 中
    if not data.get("email"):
        kiro_meta = (upstream_metadata or {}).get("kiro") or {}
        if kiro_meta.get("email"):
            data["email"] = kiro_meta["email"]
    return data


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_all() -> None:
    """Register all Kiro hooks into shared registries."""

    from src.services.model.upstream_fetcher import UpstreamModelsFetcherRegistry
    from src.services.provider.adapters.kiro.envelope import kiro_envelope
    from src.services.provider.envelope import register_envelope
    from src.services.provider.export import register_export_builder
    from src.services.provider.transport import register_transport_hook

    register_envelope("kiro", "claude:cli", kiro_envelope)
    register_envelope("kiro", "", kiro_envelope)

    register_transport_hook("kiro", "claude:cli", build_kiro_url)

    register_export_builder("kiro", kiro_export_builder)

    UpstreamModelsFetcherRegistry.register(
        provider_types=["kiro"],
        fetcher=fetch_models_kiro,
    )


__all__ = ["build_kiro_url", "fetch_models_kiro", "kiro_export_builder", "register_all"]
