from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pytest

from src.core.crypto import crypto_service
from src.api.admin.providers.summary import _compose_provider_summary
from src.core.enums import ProviderBillingType
from src.models.database import Provider
from src.services.provider_ops.proxy_probe import probe_pending_provider_proxies, probe_provider_proxy


class _FakeQuery:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


@dataclass
class _FakeDB:
    providers: list[Provider] = field(default_factory=list)
    commit_count: int = 0

    def query(self, model: type[Any]) -> _FakeQuery:
        if model is Provider:
            return _FakeQuery(self.providers)
        raise AssertionError(f"unexpected model: {model}")

    def commit(self) -> None:
        self.commit_count += 1


def _build_provider(
    *,
    provider_id: str = "provider-1",
    website: str = "https://provider-1.example.com",
    architecture_id: str = "sub2api",
    auth_type: str = "api_key",
    credentials: dict[str, str] | None = None,
    connector_config: dict[str, Any] | None = None,
    auto_imported: bool = True,
    probe_status: str = "pending",
) -> Provider:
    enc_credentials = {
        key: crypto_service.encrypt(value)
        for key, value in (credentials or {"refresh_token": "rt-1"}).items()
    }
    return Provider(
        id=provider_id,
        name="Provider One",
        provider_type="custom",
        billing_type=ProviderBillingType.PAY_AS_YOU_GO,
        website=website,
        provider_priority=0,
        keep_priority_on_conversion=False,
        enable_format_conversion=False,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        config={
            "provider_ops": {
                "architecture_id": architecture_id,
                "base_url": website,
                "connector": {
                    "auth_type": auth_type,
                    "config": dict(connector_config or {}),
                    "credentials": enc_credentials,
                },
                "actions": {"query_balance": {"enabled": True, "config": {}}},
                "schedule": {},
                "_auto_imported": auto_imported,
                "_proxy_probe_status": probe_status,
            }
        },
    )


@pytest.mark.asyncio
async def test_probe_pending_provider_proxies_persists_system_proxy_on_direct_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    async def _fake_verify_auth(
        self: Any,
        *,
        base_url: str,
        architecture_id: str,
        auth_type: Any,
        config: dict[str, Any],
        credentials: dict[str, Any],
        provider_id: str | None = None,
    ) -> dict[str, Any]:
        _ = self, base_url, architecture_id, auth_type, credentials, provider_id
        calls.append(dict(config))
        if config.get("proxy_node_id") == "proxy-node-1":
            return {"success": True, "data": {"username": "demo", "quota": 1}}
        return {"success": False, "message": "direct failed"}

    async def _fake_system_proxy() -> dict[str, Any]:
        return {"node_id": "proxy-node-1", "enabled": True}

    monkeypatch.setattr(
        "src.services.provider_ops.proxy_probe.ProviderOpsService.verify_auth",
        _fake_verify_auth,
    )
    monkeypatch.setattr(
        "src.services.provider_ops.proxy_probe.get_system_proxy_config_async",
        _fake_system_proxy,
    )

    provider = _build_provider()
    db = _FakeDB(providers=[provider])

    result = await probe_pending_provider_proxies(db=db, limit=10)

    assert result.total_selected == 1
    assert result.completed == 1
    assert result.failed == 0
    assert len(calls) == 2
    assert calls[0]["__disable_system_proxy_fallback__"] is True
    assert calls[1]["proxy_node_id"] == "proxy-node-1"
    assert provider.proxy == {"node_id": "proxy-node-1", "enabled": True}
    provider_ops = provider.config["provider_ops"]
    assert provider_ops["connector"]["config"] == {}
    assert provider_ops["_proxy_probe_status"] == "completed"
    assert provider_ops["_proxy_probe_mode"] == "system_proxy"


@pytest.mark.asyncio
async def test_probe_pending_provider_proxies_marks_direct_success_without_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_verify_auth(
        self: Any,
        *,
        base_url: str,
        architecture_id: str,
        auth_type: Any,
        config: dict[str, Any],
        credentials: dict[str, Any],
        provider_id: str | None = None,
    ) -> dict[str, Any]:
        _ = self, base_url, architecture_id, auth_type, credentials, provider_id
        return {"success": True, "data": {"username": "demo", "quota": 1}}

    monkeypatch.setattr(
        "src.services.provider_ops.proxy_probe.ProviderOpsService.verify_auth",
        _fake_verify_auth,
    )

    provider = _build_provider()
    db = _FakeDB(providers=[provider])

    result = await probe_pending_provider_proxies(db=db, limit=10)

    assert result.total_selected == 1
    assert result.completed == 1
    assert provider.proxy is None
    provider_ops = provider.config["provider_ops"]
    assert provider_ops["connector"]["config"] == {}
    assert provider_ops["_proxy_probe_status"] == "completed"
    assert provider_ops["_proxy_probe_mode"] == "direct"


@pytest.mark.asyncio
async def test_probe_pending_provider_proxies_marks_challenge_pages_for_manual_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_verify_auth(
        self: Any,
        *,
        base_url: str,
        architecture_id: str,
        auth_type: Any,
        config: dict[str, Any],
        credentials: dict[str, Any],
        provider_id: str | None = None,
    ) -> dict[str, Any]:
        _ = self, base_url, architecture_id, auth_type, config, credentials, provider_id
        return {"success": False, "message": "Cloudflare challenge page detected: arg1/acw_sc__v2"}

    async def _fake_system_proxy() -> dict[str, Any]:
        return {"node_id": "proxy-node-1", "enabled": True}

    monkeypatch.setattr(
        "src.services.provider_ops.proxy_probe.ProviderOpsService.verify_auth",
        _fake_verify_auth,
    )
    monkeypatch.setattr(
        "src.services.provider_ops.proxy_probe.get_system_proxy_config_async",
        _fake_system_proxy,
    )

    provider = _build_provider()
    db = _FakeDB(providers=[provider])

    result = await probe_pending_provider_proxies(db=db, limit=10)

    assert result.total_selected == 1
    assert result.completed == 0
    assert result.failed == 0
    assert result.skipped == 1
    assert result.results[0]["status"] == "manual_review"
    assert provider.proxy is None
    provider_ops = provider.config["provider_ops"]
    assert provider_ops["connector"]["config"] == {}
    assert provider_ops["_proxy_probe_status"] == "manual_review"
    assert provider_ops["_proxy_probe_mode"] == "challenge"
    assert "Cloudflare challenge page detected" in str(provider_ops["_proxy_probe_message"])


def test_compose_provider_summary_exposes_proxy_probe_manual_review_metadata() -> None:
    provider = _build_provider()
    provider.config["provider_ops"]["_proxy_probe_status"] = "manual_review"
    provider.config["provider_ops"]["_proxy_probe_mode"] = "challenge"
    provider.config["provider_ops"]["_proxy_probe_message"] = "Cloudflare challenge page detected"

    summary = _compose_provider_summary(
        provider=provider,
        endpoints=[],
        all_keys=[],
        total_keys=0,
        active_keys=0,
        total_models=0,
        active_models=0,
        global_model_ids=[],
    )

    assert summary.proxy_probe_status == "manual_review"
    assert summary.proxy_probe_mode == "challenge"
    assert summary.proxy_probe_message == "Cloudflare challenge page detected"


@pytest.mark.asyncio
async def test_probe_provider_proxy_returns_serializable_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_verify_auth(
        self: Any,
        *,
        base_url: str,
        architecture_id: str,
        auth_type: Any,
        config: dict[str, Any],
        credentials: dict[str, Any],
        provider_id: str | None = None,
    ) -> dict[str, Any]:
        _ = self, base_url, architecture_id, auth_type, config, credentials, provider_id
        return {"success": True, "data": {"username": "demo", "quota": 1}}

    monkeypatch.setattr(
        "src.services.provider_ops.proxy_probe.ProviderOpsService.verify_auth",
        _fake_verify_auth,
    )

    provider = _build_provider()
    db = _FakeDB(providers=[provider])

    result = await probe_provider_proxy(provider.id, db=db)

    assert result["provider_id"] == provider.id
    assert result["status"] == "completed"
    assert result["mode"] == "direct"
