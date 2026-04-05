from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from src.core.crypto import crypto_service
from src.models.database import Provider, ProviderAPIKey, ProviderEndpoint, ProviderImportTask
from src.services.provider_import.all_in_hub import (
    execute_all_in_hub_import,
    preview_all_in_hub_import,
)


class _FakeQuery:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


@dataclass
class _FakeDB:
    providers: list[Provider] = field(default_factory=list)
    endpoints: list[ProviderEndpoint] = field(default_factory=list)
    keys: list[ProviderAPIKey] = field(default_factory=list)
    tasks: list[ProviderImportTask] = field(default_factory=list)
    commit_count: int = 0
    rollback_count: int = 0

    def query(self, model: type[Any]) -> _FakeQuery:
        if model is Provider:
            return _FakeQuery(self.providers)
        if model is ProviderEndpoint:
            return _FakeQuery(self.endpoints)
        if model is ProviderAPIKey:
            return _FakeQuery(self.keys)
        if model is ProviderImportTask:
            return _FakeQuery(self.tasks)
        raise AssertionError(f"unexpected model: {model}")

    def add(self, obj: Any) -> None:
        if isinstance(obj, Provider):
            self.providers.append(obj)
            return
        if isinstance(obj, ProviderEndpoint):
            self.endpoints.append(obj)
            return
        if isinstance(obj, ProviderAPIKey):
            self.keys.append(obj)
            return
        if isinstance(obj, ProviderImportTask):
            self.tasks.append(obj)
            return
        raise AssertionError(f"unexpected add type: {type(obj)}")

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1


def test_preview_counts_direct_and_pending_records() -> None:
    payload = {
        "version": "2.0",
        "accounts": {
            "accounts": [
                {
                    "id": "acct-1",
                    "site_url": "https://provider-1.example.com",
                    "site_name": "Provider One",
                    "account_info": {"access_token": "token-1"},
                },
                {
                    "id": "acct-2",
                    "site_url": "https://provider-1.example.com",
                    "site_name": "Provider One",
                },
            ]
        },
        "direct_imports": [
            {
                "name": "primary-key",
                "baseUrl": "https://provider-1.example.com/v1",
                "apiKey": "sk-direct-1",
            }
        ],
    }

    result = preview_all_in_hub_import(payload, db=_FakeDB())

    assert result.dry_run is True
    assert result.version == "2.0"
    assert result.stats.providers_total == 1
    assert result.stats.providers_to_create == 1
    assert result.stats.endpoints_to_create == 1
    assert result.stats.direct_keys_ready == 1
    assert result.stats.pending_sources == 1
    assert result.stats.pending_tasks_to_create == 1
    assert result.stats.pending_tasks_reused == 0
    assert result.providers[0].provider_name == "Provider One"
    assert result.providers[0].provider_website == "https://provider-1.example.com"
    assert result.providers[0].endpoint_base_url == "https://provider-1.example.com/v1"


def test_preview_skips_disabled_v2_accounts() -> None:
    payload = {
        "version": "2.0",
        "accounts": {
            "accounts": [
                {
                    "id": "acct-enabled",
                    "site_url": "https://provider-1.example.com",
                    "site_name": "Provider One",
                    "disabled": False,
                    "account_info": {"access_token": "token-enabled"},
                },
                {
                    "id": "acct-disabled",
                    "site_url": "https://provider-1.example.com",
                    "site_name": "Provider One",
                    "disabled": True,
                    "account_info": {"access_token": "token-disabled"},
                },
            ]
        },
    }

    result = preview_all_in_hub_import(payload, db=_FakeDB())

    assert result.stats.providers_total == 1
    assert result.stats.pending_sources == 1
    assert result.stats.pending_tasks_to_create == 1
    assert result.providers[0].pending_source_count == 1


@pytest.mark.asyncio
async def test_execute_import_creates_provider_endpoint_key_and_pending_task_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _noop_side_effects(**_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(
        "src.services.provider_import.all_in_hub.run_create_key_side_effects",
        _noop_side_effects,
    )
    monkeypatch.setattr(
        "src.services.provider_import.all_in_hub.invalidate_models_list_cache",
        _noop_side_effects,
    )

    db = _FakeDB()
    payload = {
        "version": "2.0",
        "accounts": {
            "accounts": [
                {
                    "id": "acct-1",
                    "site_url": "https://provider-1.example.com",
                    "site_name": "Provider One",
                    "site_type": "new-api",
                    "authType": "access_token",
                    "account_info": {"id": "user-1", "username": "demo", "access_token": "token-1"},
                }
            ]
        },
        "direct_imports": [
            {
                "name": "primary-key",
                "baseUrl": "https://provider-1.example.com/v1",
                "apiKey": "sk-direct-1",
            }
        ],
    }

    first = await execute_all_in_hub_import(payload, db=db)

    assert first.dry_run is False
    assert first.stats.providers_created == 1
    assert first.stats.endpoints_created == 1
    assert first.stats.keys_created == 1
    assert first.stats.pending_sources == 1
    assert first.stats.pending_tasks_created == 1
    assert first.stats.pending_tasks_reused == 0
    assert len(db.providers) == 1
    assert len(db.endpoints) == 1
    assert len(db.keys) == 1
    assert len(db.tasks) == 1
    assert db.tasks[0].task_type == "pending_reissue"
    assert db.tasks[0].status == "pending"
    decrypted_payload = crypto_service.decrypt(db.tasks[0].credential_payload)
    assert "token-1" in decrypted_payload
    assert db.tasks[0].source_metadata["site_type"] == "new-api"
    assert db.tasks[0].source_metadata["account_id"] == "user-1"

    second = await execute_all_in_hub_import(payload, db=db)

    assert second.stats.providers_created == 0
    assert second.stats.endpoints_created == 0
    assert second.stats.keys_created == 0
    assert second.stats.keys_skipped == 1
    assert second.stats.pending_tasks_created == 0
    assert second.stats.pending_tasks_reused == 1
    assert len(db.providers) == 1
    assert len(db.endpoints) == 1
    assert len(db.keys) == 1
    assert len(db.tasks) == 1


@pytest.mark.asyncio
async def test_execute_import_creates_pending_import_task_for_cookie_only_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _noop_side_effects(**_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(
        "src.services.provider_import.all_in_hub.run_create_key_side_effects",
        _noop_side_effects,
    )
    monkeypatch.setattr(
        "src.services.provider_import.all_in_hub.invalidate_models_list_cache",
        _noop_side_effects,
    )

    db = _FakeDB()
    payload = {
        "version": "2.0",
        "accounts": {
            "accounts": [
                {
                    "id": "acct-cookie-1",
                    "site_url": "https://provider-2.example.com",
                    "site_name": "Provider Two",
                    "cookieAuth": {"sessionCookie": "cookie-1"},
                }
            ]
        },
    }

    result = await execute_all_in_hub_import(payload, db=db)

    assert result.stats.pending_sources == 1
    assert result.stats.pending_tasks_created == 1
    assert len(db.tasks) == 1
    assert db.tasks[0].task_type == "pending_import"
    assert db.tasks[0].source_kind == "all_in_hub"
    decrypted_payload = crypto_service.decrypt(db.tasks[0].credential_payload)
    assert "cookie-1" in decrypted_payload


@pytest.mark.asyncio
async def test_execute_import_treats_cookie_auth_source_as_pending_import_even_with_access_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _noop_side_effects(**_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(
        "src.services.provider_import.all_in_hub.run_create_key_side_effects",
        _noop_side_effects,
    )
    monkeypatch.setattr(
        "src.services.provider_import.all_in_hub.invalidate_models_list_cache",
        _noop_side_effects,
    )

    db = _FakeDB()
    payload = {
        "version": "2.0",
        "accounts": {
            "accounts": [
                {
                    "id": "acct-anyrouter-1",
                    "site_url": "https://anyrouter.top",
                    "site_name": "Anyrouter",
                    "site_type": "anyrouter",
                    "authType": "cookie",
                    "account_info": {
                        "id": "133664",
                        "username": "linuxdo_133664",
                        "access_token": "dashboard-token",
                    },
                    "cookieAuth": {"sessionCookie": "session=cookie-1"},
                }
            ]
        },
    }

    result = await execute_all_in_hub_import(payload, db=db)

    assert result.stats.pending_sources == 1
    assert result.stats.pending_tasks_created == 1
    assert len(db.tasks) == 1
    assert db.tasks[0].task_type == "pending_import"
    decrypted_payload = crypto_service.decrypt(db.tasks[0].credential_payload)
    assert "dashboard-token" in decrypted_payload
    assert "cookie-1" in decrypted_payload
