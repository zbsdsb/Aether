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

    def delete(self, obj: Any) -> None:
        if isinstance(obj, Provider):
            self.providers = [item for item in self.providers if item is not obj]
            return
        if isinstance(obj, ProviderEndpoint):
            self.endpoints = [item for item in self.endpoints if item is not obj]
            return
        if isinstance(obj, ProviderAPIKey):
            self.keys = [item for item in self.keys if item is not obj]
            return
        if isinstance(obj, ProviderImportTask):
            self.tasks = [item for item in self.tasks if item is not obj]
            return
        raise AssertionError(f"unexpected delete type: {type(obj)}")

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
    assert result.stats.endpoints_to_create == 3
    assert result.stats.direct_keys_ready == 1
    assert result.stats.pending_sources == 1
    assert result.stats.pending_tasks_to_create == 1
    assert result.stats.pending_tasks_reused == 0
    assert result.providers[0].provider_name == "Provider One"
    assert result.providers[0].provider_website == "https://provider-1.example.com"
    assert result.providers[0].endpoint_base_url == "https://provider-1.example.com/v1"


def test_preview_does_not_count_prefill_only_sources_as_pending_manual_work() -> None:
    payload = {
        "version": "2.0",
        "accounts": {
            "accounts": [
                {
                    "id": "acct-kfc",
                    "site_url": "https://provider-1.example.com",
                    "site_name": "Provider One",
                    "site_type": "new-api",
                    "authType": "access_token",
                    "disabled": False,
                    "account_info": {"id": "user-1", "access_token": "token-snapshot"},
                },
                {
                    "id": "acct-pending",
                    "site_url": "https://provider-1.example.com",
                    "site_name": "Provider One",
                    "site_type": "new-api",
                    "authType": "access_token",
                    "disabled": False,
                    "account_info": {"id": "user-2", "access_token": "token-pending"},
                },
            ]
        },
        "accountKeySnapshots": [
            {
                "accountId": "acct-kfc",
                "accountName": "Provider One",
                "baseUrl": "https://provider-1.example.com",
                "siteType": "new-api",
                "tokens": [
                    {"id": 101, "name": "snapshot-primary", "key": "sk-snapshot-1"},
                    {"id": 102, "name": "snapshot-secondary", "key": "sk-snapshot-2"},
                ],
            }
        ],
    }

    result = preview_all_in_hub_import(payload, db=_FakeDB())

    assert result.stats.providers_total == 1
    assert result.stats.direct_keys_ready == 2
    assert result.stats.pending_sources == 1
    assert result.stats.pending_tasks_to_create == 1
    assert result.providers[0].direct_key_count == 2
    assert result.providers[0].pending_source_count == 1
    assert len(result.manual_items) == 1
    assert result.manual_items[0].source_id == "acct-pending"


def test_preview_adds_claude_candidates_when_records_contain_claude_hints() -> None:
    payload = {
        "version": "2.0",
        "accounts": {
            "accounts": [
                {
                    "id": "acct-claude-1",
                    "site_url": "https://provider-claude.example.com",
                    "site_name": "Claude Hub",
                    "site_type": "anthropic-compatible",
                    "account_info": {"access_token": "token-1"},
                }
            ]
        },
    }

    result = preview_all_in_hub_import(payload, db=_FakeDB())

    assert result.stats.providers_total == 1
    assert result.stats.endpoints_to_create == 5


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


def test_preview_normalizes_nihaoapi_endpoint_to_api_subdomain() -> None:
    payload = {
        "version": "2.0",
        "accounts": {
            "accounts": [
                {
                    "id": "acct-nihao-1",
                    "site_url": "https://nih.cc",
                    "site_name": "NihaoAPI",
                    "site_type": "new-api",
                    "authType": "access_token",
                    "account_info": {"id": "user-951", "access_token": "token-1"},
                }
            ]
        },
    }

    result = preview_all_in_hub_import(payload, db=_FakeDB())

    assert result.providers[0].provider_website == "https://nih.cc"
    assert result.providers[0].endpoint_base_url == "https://api.nih.cc"


def test_preview_creates_prefill_only_task_for_same_account_with_snapshot_tokens() -> None:
    payload = {
        "version": "2.0",
        "accounts": {
            "accounts": [
                {
                    "id": "acct-snapshot",
                    "site_url": "https://provider-1.example.com",
                    "site_name": "Provider One",
                    "site_type": "new-api",
                    "authType": "access_token",
                    "disabled": False,
                    "account_info": {"id": "user-1", "access_token": "token-snapshot"},
                },
                {
                    "id": "acct-pending",
                    "site_url": "https://provider-1.example.com",
                    "site_name": "Provider One",
                    "site_type": "new-api",
                    "authType": "access_token",
                    "disabled": False,
                    "account_info": {"id": "user-2", "access_token": "token-pending"},
                },
            ]
        },
        "accountKeySnapshots": [
            {
                "accountId": "acct-snapshot",
                "accountName": "Provider One",
                "baseUrl": "https://provider-1.example.com",
                "siteType": "new-api",
                "tokens": [
                    {"id": 101, "name": "snapshot-primary", "key": "sk-snapshot-1"},
                    {"id": 102, "name": "snapshot-secondary", "key": "sk-snapshot-2"},
                ],
            }
        ],
    }

    result = preview_all_in_hub_import(payload, db=_FakeDB())

    assert result.stats.providers_total == 1
    assert result.stats.direct_keys_ready == 2
    assert result.stats.pending_sources == 1
    assert result.stats.pending_tasks_to_create == 1
    assert result.providers[0].direct_key_count == 2
    assert result.providers[0].pending_source_count == 1
    assert len(result.manual_items) == 1
    assert result.manual_items[0].source_id == "acct-pending"


def test_preview_reads_sub2api_refresh_token_as_importable_auth() -> None:
    payload = {
        "version": "2.0",
        "accounts": {
            "accounts": [
                {
                    "id": "acct-sub2-1",
                    "site_url": "https://sub.example.com",
                    "site_name": "Sub Provider",
                    "site_type": "sub2api",
                    "authType": "access_token",
                    "account_info": {
                        "id": 9527,
                        "username": "linuxdo_9527",
                        "access_token": "access-sub2-1",
                    },
                    "sub2apiAuth": {
                        "refreshToken": "rt-sub2-1",
                        "tokenExpiresAt": 1775613625972,
                    },
                }
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
    assert first.stats.endpoints_created == 3
    assert first.stats.keys_created == 1
    assert first.stats.pending_sources == 1
    assert first.stats.pending_tasks_created == 1
    assert first.stats.pending_tasks_reused == 0
    assert len(db.providers) == 1
    assert len(db.endpoints) == 3
    assert len(db.keys) == 1
    assert len(db.tasks) == 2
    assert sorted(endpoint.api_format for endpoint in db.endpoints) == [
        "openai:chat",
        "openai:cli",
        "openai:compact",
    ]
    assert sorted(db.keys[0].api_formats) == [
        "openai:chat",
        "openai:cli",
        "openai:compact",
    ]
    task_types = {task.task_type for task in db.tasks}
    assert task_types == {"pending_reissue", "imported_auth_prefill"}
    pending_reissue = next(task for task in db.tasks if task.task_type == "pending_reissue")
    assert pending_reissue.status == "pending"
    decrypted_payload = crypto_service.decrypt(pending_reissue.credential_payload)
    assert "token-1" in decrypted_payload
    assert pending_reissue.source_metadata["site_type"] == "new-api"
    assert pending_reissue.source_metadata["account_id"] == "user-1"

    second = await execute_all_in_hub_import(payload, db=db)

    assert second.stats.providers_created == 0
    assert second.stats.endpoints_created == 0
    assert second.stats.keys_created == 0
    assert second.stats.keys_skipped == 1
    assert second.stats.pending_tasks_created == 0
    assert second.stats.pending_tasks_reused == 1
    assert len(db.providers) == 1
    assert len(db.endpoints) == 3
    assert len(db.keys) == 1
    assert len(db.tasks) == 2


@pytest.mark.asyncio
async def test_execute_import_adds_claude_candidates_when_record_contains_claude_hint(
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
                    "id": "acct-claude-1",
                    "site_url": "https://provider-claude.example.com",
                    "site_name": "Claude Hub",
                    "site_type": "anthropic-compatible",
                    "authType": "access_token",
                    "account_info": {"id": "user-1", "username": "demo", "access_token": "token-1"},
                }
            ]
        },
        "direct_imports": [
            {
                "name": "claude-key",
                "baseUrl": "https://provider-claude.example.com/v1",
                "apiKey": "sk-claude-1",
            }
        ],
    }

    result = await execute_all_in_hub_import(payload, db=db)

    assert result.stats.endpoints_created == 5
    assert sorted(endpoint.api_format for endpoint in db.endpoints) == [
        "claude:chat",
        "claude:cli",
        "openai:chat",
        "openai:cli",
        "openai:compact",
    ]
    assert sorted(db.keys[0].api_formats) == [
        "claude:chat",
        "claude:cli",
        "openai:chat",
        "openai:cli",
        "openai:compact",
    ]


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

    assert result.stats.pending_sources == 0
    assert result.stats.pending_tasks_created == 0
    assert len(db.tasks) == 1
    assert db.tasks[0].task_type == "imported_auth_prefill"
    decrypted_payload = crypto_service.decrypt(db.tasks[0].credential_payload)
    assert "dashboard-token" in decrypted_payload
    assert "cookie-1" in decrypted_payload


@pytest.mark.asyncio
async def test_execute_import_creates_prefill_only_task_for_same_account_with_snapshot_tokens(
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
                    "id": "acct-snapshot",
                    "site_url": "https://provider-1.example.com",
                    "site_name": "Provider One",
                    "site_type": "new-api",
                    "authType": "access_token",
                    "disabled": False,
                    "account_info": {"id": "user-1", "access_token": "token-snapshot"},
                },
                {
                    "id": "acct-pending",
                    "site_url": "https://provider-1.example.com",
                    "site_name": "Provider One",
                    "site_type": "new-api",
                    "authType": "access_token",
                    "disabled": False,
                    "account_info": {"id": "user-2", "access_token": "token-pending"},
                },
            ]
        },
        "accountKeySnapshots": [
            {
                "accountId": "acct-snapshot",
                "accountName": "Provider One",
                "baseUrl": "https://provider-1.example.com",
                "siteType": "new-api",
                "tokens": [
                    {"id": 101, "name": "snapshot-primary", "key": "sk-snapshot-1"},
                    {"id": 102, "name": "snapshot-secondary", "key": "sk-snapshot-2"},
                ],
            }
        ],
    }

    result = await execute_all_in_hub_import(payload, db=db)

    assert result.stats.keys_created == 2
    assert result.stats.pending_sources == 1
    assert result.stats.pending_tasks_created == 1
    assert len(db.keys) == 2
    assert {crypto_service.decrypt(key.api_key) for key in db.keys} == {"sk-snapshot-1", "sk-snapshot-2"}
    assert {key.name for key in db.keys} == {"snapshot-primary", "snapshot-secondary"}
    assert len(db.tasks) == 3
    assert {task.source_id for task in db.tasks} == {"acct-snapshot", "acct-pending"}
    task_by_source = {task.source_id: task for task in db.tasks}
    snapshot_tasks = [task for task in db.tasks if task.source_id == "acct-snapshot"]
    pending_tasks = [task for task in db.tasks if task.source_id == "acct-pending"]
    assert {task.task_type for task in snapshot_tasks} == {"imported_auth_prefill"}
    assert snapshot_tasks[0].source_metadata["account_id"] == "user-1"
    assert {task.task_type for task in pending_tasks} == {"pending_reissue", "imported_auth_prefill"}
    assert all(task.source_metadata["account_id"] == "user-2" for task in pending_tasks)


@pytest.mark.asyncio
async def test_execute_import_schedules_background_model_fetch_for_direct_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _noop_side_effects(**_kwargs: Any) -> None:
        return None

    scheduled_key_ids_batches: list[list[str]] = []

    def _fake_schedule(key_ids: list[str]) -> None:
        scheduled_key_ids_batches.append(list(key_ids))

    monkeypatch.setattr(
        "src.services.provider_import.all_in_hub.run_create_key_side_effects",
        _noop_side_effects,
    )
    monkeypatch.setattr(
        "src.services.provider_import.all_in_hub.invalidate_models_list_cache",
        _noop_side_effects,
    )
    monkeypatch.setattr(
        "src.services.provider_import.all_in_hub._schedule_imported_key_model_fetches",
        _fake_schedule,
    )

    db = _FakeDB()
    payload = {
        "version": "2.0",
        "direct_imports": [
            {
                "name": "provider-one-direct",
                "baseUrl": "https://provider-1.example.com/v1",
                "apiKey": "sk-direct-verification-fail",
            }
        ],
    }

    result = await execute_all_in_hub_import(payload, db=db)

    assert result.stats.keys_created == 1
    assert result.manual_items == []
    assert len(db.keys) == 1
    assert db.keys[0].is_active is True
    assert scheduled_key_ids_batches == [[str(db.keys[0].id)]]


@pytest.mark.asyncio
async def test_execute_import_persists_sub2api_refresh_token_in_task_payload(
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
                    "id": "acct-sub2-1",
                    "site_url": "https://sub.example.com",
                    "site_name": "Sub Provider",
                    "site_type": "sub2api",
                    "authType": "access_token",
                    "account_info": {
                        "id": 9527,
                        "username": "linuxdo_9527",
                        "access_token": "access-sub2-1",
                    },
                    "sub2apiAuth": {
                        "refreshToken": "rt-sub2-1",
                        "tokenExpiresAt": 1775613625972,
                    },
                }
            ]
        },
    }

    result = await execute_all_in_hub_import(payload, db=db)

    assert result.stats.pending_sources == 1
    assert result.stats.pending_tasks_created == 1
    assert len(db.tasks) == 2

    task_types = {task.task_type for task in db.tasks}
    assert task_types == {"pending_reissue", "imported_auth_prefill"}

    pending_reissue = next(task for task in db.tasks if task.task_type == "pending_reissue")
    assert pending_reissue.source_metadata["site_type"] == "sub2api"
    assert pending_reissue.source_metadata["account_id"] == "9527"

    decrypted_payload = crypto_service.decrypt(pending_reissue.credential_payload)
    assert '"access_token": "access-sub2-1"' in decrypted_payload
    assert '"refresh_token": "rt-sub2-1"' in decrypted_payload


@pytest.mark.asyncio
async def test_execute_import_disables_matched_existing_provider_when_backup_account_is_disabled(
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

    provider = Provider(
        id="provider-existing",
        name="Provider One",
        website="https://provider-1.example.com",
        is_active=True,
    )
    endpoint = ProviderEndpoint(
        id="endpoint-existing",
        provider_id=provider.id,
        api_format="openai:chat",
        api_family="openai",
        endpoint_kind="chat",
        base_url="https://provider-1.example.com/v1",
        is_active=True,
    )
    db = _FakeDB(providers=[provider], endpoints=[endpoint])
    payload = {
        "version": "2.0",
        "accounts": {
            "accounts": [
                {
                    "id": "acct-disabled",
                    "site_url": "https://provider-1.example.com",
                    "site_name": "Provider One",
                    "disabled": True,
                    "account_info": {},
                },
            ]
        },
    }

    result = await execute_all_in_hub_import(payload, db=db)

    assert result.stats.providers_created == 0
    assert db.providers[0].is_active is False


@pytest.mark.asyncio
async def test_execute_import_deletes_missing_imported_keys_for_matched_provider_when_backup_has_plaintext_keys(
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

    provider = Provider(
        id="provider-existing",
        name="Provider One",
        website="https://provider-1.example.com",
        is_active=True,
    )
    endpoint = ProviderEndpoint(
        id="endpoint-existing",
        provider_id=provider.id,
        api_format="openai:chat",
        api_family="openai",
        endpoint_kind="chat",
        base_url="https://provider-1.example.com/v1",
        is_active=True,
    )
    keep_key = ProviderAPIKey(
        id="key-keep",
        provider_id=provider.id,
        auth_type="api_key",
        api_key=crypto_service.encrypt("sk-keep"),
        api_formats=["openai:chat"],
        name="keep",
        note="Imported from all-in-hub",
        is_active=True,
    )
    delete_key = ProviderAPIKey(
        id="key-delete",
        provider_id=provider.id,
        auth_type="api_key",
        api_key=crypto_service.encrypt("sk-delete"),
        api_formats=["openai:chat"],
        name="delete",
        note="Imported from all-in-hub",
        is_active=True,
    )
    manual_key = ProviderAPIKey(
        id="key-manual",
        provider_id=provider.id,
        auth_type="api_key",
        api_key=crypto_service.encrypt("sk-manual"),
        api_formats=["openai:chat"],
        name="manual",
        note="Manual key",
        is_active=True,
    )
    db = _FakeDB(
        providers=[provider],
        endpoints=[endpoint],
        keys=[keep_key, delete_key, manual_key],
    )
    payload = {
        "version": "2.0",
        "direct_imports": [
            {
                "name": "keep",
                "baseUrl": "https://provider-1.example.com/v1",
                "apiKey": "sk-keep",
            }
        ],
    }

    result = await execute_all_in_hub_import(payload, db=db)

    assert result.stats.keys_created == 0
    assert result.stats.keys_skipped == 1
    assert {key.id for key in db.keys} == {"key-keep", "key-manual"}
    assert {crypto_service.decrypt(key.api_key) for key in db.keys} == {"sk-keep", "sk-manual"}


@pytest.mark.asyncio
async def test_execute_import_keeps_existing_imported_keys_when_backup_key_is_masked(
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

    provider = Provider(
        id="provider-existing",
        name="Provider One",
        website="https://provider-1.example.com",
        is_active=True,
    )
    endpoint = ProviderEndpoint(
        id="endpoint-existing",
        provider_id=provider.id,
        api_format="openai:chat",
        api_family="openai",
        endpoint_kind="chat",
        base_url="https://provider-1.example.com/v1",
        is_active=True,
    )
    old_imported_key = ProviderAPIKey(
        id="key-old",
        provider_id=provider.id,
        auth_type="api_key",
        api_key=crypto_service.encrypt("sk-old"),
        api_formats=["openai:chat"],
        name="old",
        note="Imported from all-in-hub",
        is_active=True,
    )
    db = _FakeDB(
        providers=[provider],
        endpoints=[endpoint],
        keys=[old_imported_key],
    )
    payload = {
        "version": "2.0",
        "accountKeySnapshots": [
            {
                "accountId": "acct-1",
                "accountName": "Provider One",
                "baseUrl": "https://provider-1.example.com/v1",
                "tokens": [
                    {"id": "token-1", "name": "masked", "key": "sk-****-masked"},
                ],
            }
        ],
    }

    result = await execute_all_in_hub_import(payload, db=db)

    assert result.stats.keys_created == 0
    assert {key.id for key in db.keys} == {"key-old"}
    assert crypto_service.decrypt(db.keys[0].api_key) == "sk-old"
