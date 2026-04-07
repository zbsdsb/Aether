from __future__ import annotations

from dataclasses import dataclass

from src.core.api_format.enums import ApiFamily, EndpointKind


@dataclass(frozen=True, slots=True)
class EndpointCandidate:
    api_format: str
    api_family: str
    endpoint_kind: str
    reason: str


def _candidate(api_family: ApiFamily, endpoint_kind: EndpointKind, reason: str) -> EndpointCandidate:
    return EndpointCandidate(
        api_format=f"{api_family.value}:{endpoint_kind.value}",
        api_family=api_family.value,
        endpoint_kind=endpoint_kind.value,
        reason=reason,
    )


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _has_family_hint(*, site_types: list[str], labels: list[str], endpoint_base_url: str) -> tuple[bool, bool]:
    site_type_values = " ".join(site_types).lower()
    label_values = " ".join(labels).lower()
    base_url = str(endpoint_base_url or "").lower()
    combined = " ".join(value for value in (site_type_values, label_values, base_url) if value)

    has_claude_hint = _contains_any(combined, ("claude", "anthropic"))
    has_gemini_hint = _contains_any(combined, ("gemini", "google", "vertex"))
    return has_claude_hint, has_gemini_hint


def resolve_endpoint_candidates(
    *,
    provider_name: str,
    endpoint_base_url: str,
    site_types: list[str],
    labels: list[str],
) -> list[EndpointCandidate]:
    candidates: list[EndpointCandidate] = [
        _candidate(ApiFamily.OPENAI, EndpointKind.CHAT, "default_openai"),
        _candidate(ApiFamily.OPENAI, EndpointKind.CLI, "default_openai"),
        _candidate(ApiFamily.OPENAI, EndpointKind.COMPACT, "default_openai"),
    ]

    has_claude_hint, has_gemini_hint = _has_family_hint(
        site_types=site_types,
        labels=[provider_name, *labels],
        endpoint_base_url=endpoint_base_url,
    )

    if has_claude_hint:
        candidates.extend(
            [
                _candidate(ApiFamily.CLAUDE, EndpointKind.CHAT, "matched_claude_hint"),
                _candidate(ApiFamily.CLAUDE, EndpointKind.CLI, "matched_claude_hint"),
            ]
        )

    if has_gemini_hint:
        candidates.extend(
            [
                _candidate(ApiFamily.GEMINI, EndpointKind.CHAT, "matched_gemini_hint"),
                _candidate(ApiFamily.GEMINI, EndpointKind.CLI, "matched_gemini_hint"),
            ]
        )

    unique_candidates: list[EndpointCandidate] = []
    seen_formats: set[str] = set()
    for candidate in candidates:
        if candidate.api_format in seen_formats:
            continue
        seen_formats.add(candidate.api_format)
        unique_candidates.append(candidate)
    return unique_candidates
