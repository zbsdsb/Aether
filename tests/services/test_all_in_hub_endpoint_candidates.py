from __future__ import annotations

from src.services.provider_import.endpoint_candidates import resolve_endpoint_candidates


def test_default_candidates_include_openai_triplet() -> None:
    candidates = resolve_endpoint_candidates(
        provider_name="Provider One",
        endpoint_base_url="https://provider-1.example.com/v1",
        site_types=[],
        labels=[],
    )

    assert [candidate.api_format for candidate in candidates] == [
        "openai:chat",
        "openai:cli",
        "openai:compact",
    ]


def test_candidates_append_claude_when_claude_hint_present() -> None:
    candidates = resolve_endpoint_candidates(
        provider_name="Claude Hub",
        endpoint_base_url="https://provider-1.example.com/v1",
        site_types=["anthropic-compatible"],
        labels=["claude-sonnet-4"],
    )

    assert [candidate.api_format for candidate in candidates] == [
        "openai:chat",
        "openai:cli",
        "openai:compact",
        "claude:chat",
        "claude:cli",
    ]


def test_candidates_append_gemini_when_gemini_hint_present() -> None:
    candidates = resolve_endpoint_candidates(
        provider_name="Gemini Hub",
        endpoint_base_url="https://provider-1.example.com/v1",
        site_types=["gemini-compatible"],
        labels=["gemini-2.5-pro"],
    )

    assert [candidate.api_format for candidate in candidates] == [
        "openai:chat",
        "openai:cli",
        "openai:compact",
        "gemini:chat",
        "gemini:cli",
    ]


def test_candidates_do_not_add_cross_family_without_hint() -> None:
    candidates = resolve_endpoint_candidates(
        provider_name="OpenAI Hub",
        endpoint_base_url="https://provider-1.example.com/v1",
        site_types=["openai-compatible"],
        labels=[],
    )

    assert all(
        candidate.api_format
        not in {"claude:chat", "claude:cli", "gemini:chat", "gemini:cli"}
        for candidate in candidates
    )
