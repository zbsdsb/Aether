from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.models.database import Provider, ProviderAPIKey, ProviderEndpoint
from src.api.admin.provider_query import _sync_provider_capabilities_from_models


@dataclass
class _FakeDB:
    endpoints: list[ProviderEndpoint] = field(default_factory=list)
    commit_count: int = 0

    def add(self, obj: Any) -> None:
        if isinstance(obj, ProviderEndpoint):
            self.endpoints.append(obj)
            return
        raise AssertionError(f"unexpected add type: {type(obj)}")

    def commit(self) -> None:
        self.commit_count += 1


def test_sync_provider_capabilities_adds_missing_endpoints_and_key_formats() -> None:
    provider = Provider(
        id="provider-1",
        name="Provider One",
        provider_type="custom",
        billing_type="pay_as_you_go",
    )
    endpoint = ProviderEndpoint(
        id="endpoint-1",
        provider_id="provider-1",
        api_format="openai:chat",
        api_family="openai",
        endpoint_kind="chat",
        base_url="https://provider-1.example.com",
    )
    key = ProviderAPIKey(
        id="key-1",
        provider_id="provider-1",
        api_formats=["openai:chat"],
        auth_type="api_key",
        api_key="enc",
        name="Key One",
    )
    db = _FakeDB(endpoints=[endpoint])

    result = _sync_provider_capabilities_from_models(
        db=db,
        provider=provider,
        provider_keys=[key],
        provider_endpoints=db.endpoints,
        models=[
            {"id": "grok-4", "api_formats": ["openai:chat", "openai:cli"]},
            {"id": "grok-4.1-thinking", "api_format": "openai:compact"},
        ],
    )

    assert sorted(key.api_formats or []) == ["openai:chat", "openai:cli", "openai:compact"]
    assert sorted(item.api_format for item in db.endpoints) == [
        "openai:chat",
        "openai:cli",
        "openai:compact",
    ]
    assert result["created_endpoint_formats"] == ["openai:cli", "openai:compact"]
    assert result["updated_key_ids"] == ["key-1"]


def test_sync_provider_capabilities_never_deletes_existing_endpoints() -> None:
    provider = Provider(
        id="provider-1",
        name="Provider One",
        provider_type="custom",
        billing_type="pay_as_you_go",
    )
    endpoint_chat = ProviderEndpoint(
        id="endpoint-chat",
        provider_id="provider-1",
        api_format="openai:chat",
        api_family="openai",
        endpoint_kind="chat",
        base_url="https://provider-1.example.com",
    )
    endpoint_cli = ProviderEndpoint(
        id="endpoint-cli",
        provider_id="provider-1",
        api_format="openai:cli",
        api_family="openai",
        endpoint_kind="cli",
        base_url="https://provider-1.example.com",
    )
    key = ProviderAPIKey(
        id="key-1",
        provider_id="provider-1",
        api_formats=["openai:chat", "openai:cli"],
        auth_type="api_key",
        api_key="enc",
        name="Key One",
    )
    db = _FakeDB(endpoints=[endpoint_chat, endpoint_cli])

    result = _sync_provider_capabilities_from_models(
        db=db,
        provider=provider,
        provider_keys=[key],
        provider_endpoints=db.endpoints,
        models=[{"id": "grok-4", "api_formats": ["openai:chat"]}],
    )

    assert sorted(item.api_format for item in db.endpoints) == ["openai:chat", "openai:cli"]
    assert key.api_formats == ["openai:chat", "openai:cli"]
    assert result["created_endpoint_formats"] == []
    assert result["updated_key_ids"] == []


def test_sync_provider_capabilities_infers_gemini_formats_from_model_names() -> None:
    provider = Provider(
        id="provider-1",
        name="Provider One",
        provider_type="custom",
        billing_type="pay_as_you_go",
    )
    endpoint = ProviderEndpoint(
        id="endpoint-1",
        provider_id="provider-1",
        api_format="openai:chat",
        api_family="openai",
        endpoint_kind="chat",
        base_url="https://provider-1.example.com",
    )
    key = ProviderAPIKey(
        id="key-1",
        provider_id="provider-1",
        api_formats=["openai:chat"],
        auth_type="api_key",
        api_key="enc",
        name="Key One",
    )
    db = _FakeDB(endpoints=[endpoint])

    result = _sync_provider_capabilities_from_models(
        db=db,
        provider=provider,
        provider_keys=[key],
        provider_endpoints=db.endpoints,
        models=[
            {"id": "gemini-2.0-flash", "api_formats": ["openai:chat"]},
            {"id": "gemini-2.0-flash-lite", "api_format": "openai:chat"},
        ],
    )

    assert "gemini:chat" in (key.api_formats or [])
    assert "gemini:cli" in (key.api_formats or [])
    assert sorted(item.api_format for item in db.endpoints) == [
        "gemini:chat",
        "gemini:cli",
        "openai:chat",
    ]
    assert result["created_endpoint_formats"] == ["gemini:chat", "gemini:cli"]


def test_sync_provider_capabilities_infers_claude_formats_from_model_names() -> None:
    provider = Provider(
        id="provider-2",
        name="Provider Two",
        provider_type="custom",
        billing_type="pay_as_you_go",
    )
    endpoint = ProviderEndpoint(
        id="endpoint-1",
        provider_id="provider-2",
        api_format="openai:chat",
        api_family="openai",
        endpoint_kind="chat",
        base_url="https://provider-2.example.com",
    )
    key = ProviderAPIKey(
        id="key-2",
        provider_id="provider-2",
        api_formats=["openai:chat"],
        auth_type="api_key",
        api_key="enc",
        name="Key Two",
    )
    db = _FakeDB(endpoints=[endpoint])

    result = _sync_provider_capabilities_from_models(
        db=db,
        provider=provider,
        provider_keys=[key],
        provider_endpoints=db.endpoints,
        models=[
            {"id": "claude-sonnet-4.5", "api_formats": ["openai:chat"]},
        ],
    )

    assert "claude:chat" in (key.api_formats or [])
    assert "claude:cli" in (key.api_formats or [])
    assert sorted(item.api_format for item in db.endpoints) == [
        "claude:chat",
        "claude:cli",
        "openai:chat",
    ]
    assert result["created_endpoint_formats"] == ["claude:chat", "claude:cli"]


def test_sync_provider_capabilities_updates_key_formats_from_each_keys_models() -> None:
    provider = Provider(
        id="provider-3",
        name="Provider Three",
        provider_type="custom",
        billing_type="pay_as_you_go",
    )
    endpoint = ProviderEndpoint(
        id="endpoint-1",
        provider_id="provider-3",
        api_format="openai:chat",
        api_family="openai",
        endpoint_kind="chat",
        base_url="https://provider-3.example.com",
    )
    openai_only_key = ProviderAPIKey(
        id="key-openai",
        provider_id="provider-3",
        api_formats=["openai:chat"],
        auth_type="api_key",
        api_key="enc-openai",
        name="OpenAI Only",
    )
    gemini_key = ProviderAPIKey(
        id="key-gemini",
        provider_id="provider-3",
        api_formats=["openai:chat"],
        auth_type="api_key",
        api_key="enc-gemini",
        name="Gemini Key",
    )
    db = _FakeDB(endpoints=[endpoint])

    result = _sync_provider_capabilities_from_models(
        db=db,
        provider=provider,
        provider_keys=[openai_only_key, gemini_key],
        provider_endpoints=db.endpoints,
        models=[
            {"id": "gpt-5.4", "api_formats": ["openai:chat"]},
            {"id": "gemini-2.0-flash", "api_formats": ["openai:chat"]},
        ],
        key_models_by_key_id={
            "key-openai": [
                {"id": "gpt-5.4", "api_formats": ["openai:chat"]},
            ],
            "key-gemini": [
                {"id": "gemini-2.0-flash", "api_formats": ["openai:chat"]},
            ],
        },
    )

    assert openai_only_key.api_formats == ["openai:chat"]
    assert "gemini:chat" in (gemini_key.api_formats or [])
    assert "gemini:cli" in (gemini_key.api_formats or [])
    assert sorted(item.api_format for item in db.endpoints) == [
        "gemini:chat",
        "gemini:cli",
        "openai:chat",
    ]
    assert result["updated_key_ids"] == ["key-gemini"]
