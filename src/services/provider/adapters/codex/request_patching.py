"""
Codex provider request patching helpers (standalone / passthrough path).

In the main request pipeline, Codex-specific transformations are handled by the
``openai:cli`` normalizer with ``target_variant="codex"`` (triggered automatically
via ``register_behavior_variant("codex", same_format=True)``).

This module provides an **equivalent** standalone patcher for contexts where the full
normalizer pipeline is not used (e.g. external tooling, one-off scripts, or future
passthrough-only paths). It is intentionally kept in sync with the normalizer logic.

Transformations applied:
- Force ``store=false`` (avoid persistence features not supported by some gateways).
- Ensure ``instructions`` exists (Codex expects it in some deployments).
- Convert ``role=system`` messages to ``role=developer`` (Codex may not accept ``system``).
- Drop request parameters known to be rejected by Codex gateways.
- Ensure ``include`` contains ``"reasoning.encrypted_content"`` for parity with CLI behavior.
"""

from __future__ import annotations

from typing import Any

from src.core.provider_types import ProviderType

_REJECTED_PARAMS: frozenset[str] = frozenset(
    {
        "max_output_tokens",
        "max_completion_tokens",
        "max_tokens",
        "temperature",
        "top_p",
        "service_tier",
    }
)

_REQUIRED_INCLUDE_ITEM = "reasoning.encrypted_content"


def patch_openai_cli_request_for_codex(request_body: dict[str, Any]) -> dict[str, Any]:
    """
    Patch an OpenAI CLI (Responses API style) request body for Codex gateways.

    This function never mutates the input object.
    """
    out: dict[str, Any] = dict(request_body)

    for k in _REJECTED_PARAMS:
        out.pop(k, None)

    # Codex gateways often reject/ignore persistence; be explicit.
    out["store"] = False

    # Ensure instructions exists (some gateways require it even if empty).
    instructions = out.get("instructions")
    if not isinstance(instructions, str):
        out["instructions"] = "You are a helpful coding assistant."

    # Convert "system" role to "developer" (Codex behavior).
    input_items = out.get("input")
    if isinstance(input_items, list):
        patched_items: list[Any] = []
        for item in input_items:
            if isinstance(item, dict):
                patched = dict(item)
                if patched.get("role") == "system":
                    patched["role"] = "developer"
                patched_items.append(patched)
            else:
                patched_items.append(item)
        out["input"] = patched_items

    # Ensure required include item exists.
    include = out.get("include")
    if include is None:
        out["include"] = [_REQUIRED_INCLUDE_ITEM]
    elif isinstance(include, str):
        out["include"] = (
            [include] if include == _REQUIRED_INCLUDE_ITEM else [include, _REQUIRED_INCLUDE_ITEM]
        )
    elif isinstance(include, (list, tuple, set)):
        include_list = list(include)
        if _REQUIRED_INCLUDE_ITEM not in include_list:
            include_list.append(_REQUIRED_INCLUDE_ITEM)
        out["include"] = include_list
    else:
        # Unknown type; overwrite to keep behavior deterministic.
        out["include"] = [_REQUIRED_INCLUDE_ITEM]

    return out


def maybe_patch_request_for_codex(
    *,
    provider_type: str | None,
    provider_api_format: str | None,
    request_body: Any,
) -> Any:
    """
    Conditionally patch request body for Codex gateways.

    No-op for:
    - Non-Codex providers
    - Non OpenAI CLI / Responses-style endpoints
    - Non-dict request bodies
    """
    if (provider_type or "").lower() != ProviderType.CODEX:
        return request_body
    if (provider_api_format or "").lower() != "openai:cli":
        return request_body
    if not isinstance(request_body, dict):
        return request_body
    return patch_openai_cli_request_for_codex(request_body)


__all__ = [
    "maybe_patch_request_for_codex",
    "patch_openai_cli_request_for_codex",
]
