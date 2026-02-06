"""Provider behavior resolver.

Keep provider-specific quirks centralized so handler code stays generic.

Concepts:
- envelope: wire-level request/response wrappers and transport side-effects
- same_format_variant: subtle same-format differences (e.g. Codex)
- cross_format_variant: cross-format conversion tweaks (e.g. Antigravity thinking blocks)
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.provider_types import normalize_provider_type
from src.services.provider.envelope import ProviderEnvelope, get_provider_envelope

# --- Behavior Variant Registries ---
_same_format_variants: set[str] = set()
_cross_format_variants: set[str] = set()


def register_behavior_variant(
    provider_type: str,
    *,
    same_format: bool = False,
    cross_format: bool = False,
) -> None:
    """注册 provider 的格式变体标志。

    - same_format: 同格式下有微妙差异（如 Codex 的 OpenAI Responses 变体）
    - cross_format: 跨格式转换时有特殊处理（如 Antigravity thinking blocks）
    """
    pt = normalize_provider_type(provider_type)
    if same_format:
        _same_format_variants.add(pt)
    if cross_format:
        _cross_format_variants.add(pt)


@dataclass(frozen=True, slots=True)
class ProviderBehavior:
    provider_type: str
    envelope: ProviderEnvelope | None
    same_format_variant: str | None
    cross_format_variant: str | None


def get_provider_behavior(
    *,
    provider_type: str | None,
    endpoint_sig: str | None,
) -> ProviderBehavior:
    pt = normalize_provider_type(provider_type)
    envelope = get_provider_envelope(provider_type=pt, endpoint_sig=endpoint_sig)

    same_format_variant = pt if pt in _same_format_variants else None
    cross_format_variant = pt if pt in _cross_format_variants else None

    return ProviderBehavior(
        provider_type=pt,
        envelope=envelope,
        same_format_variant=same_format_variant,
        cross_format_variant=cross_format_variant,
    )


# Behavior variants are registered by provider plugin.register_all()
# (called from envelope.py bootstrap)

__all__ = ["ProviderBehavior", "get_provider_behavior", "register_behavior_variant"]
