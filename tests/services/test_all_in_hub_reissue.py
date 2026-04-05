from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from src.core.crypto import crypto_service
from src.models.database import Provider, ProviderAPIKey, ProviderEndpoint, ProviderImportTask
from src.services.provider_import.reissue import (
    detect_import_task_strategy,
    _find_new_api_token,
    _probe_new_api_compatibility,
    execute_all_in_hub_import_tasks,
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


def _build_task(
    *,
    task_id: str = "task-1",
    provider_id: str = "provider-1",
    endpoint_id: str = "endpoint-1",
    task_type: str = "pending_reissue",
    site_type: str = "new-api",
    access_token: str | None = "access-1",
    session_cookie: str | None = None,
    account_id: str | None = "user-1",
    source_id: str = "acct-1",
    status: str = "pending",
) -> ProviderImportTask:
    payload = crypto_service.encrypt(
        '{"access_token": %s, "session_cookie": %s}'
        % (
            f'"{access_token}"' if access_token is not None else "null",
            f'"{session_cookie}"' if session_cookie is not None else "null",
        )
    )
    return ProviderImportTask(
        id=task_id,
        provider_id=provider_id,
        endpoint_id=endpoint_id,
        task_type=task_type,
        status=status,
        source_kind="all_in_hub",
        source_id=source_id,
        source_name="Provider One",
        source_origin="https://provider-1.example.com",
        credential_payload=payload,
        source_metadata={
            "site_type": site_type,
            "account_id": account_id,
            "endpoint_base_url": "https://provider-1.example.com",
            "provider_name": "Provider One",
        },
        retry_count=0,
        last_error=None,
        last_attempt_at=None,
        completed_at=None,
    )


def test_detect_site_strategy_for_new_api_pending_reissue() -> None:
    task = _build_task()

    strategy = detect_import_task_strategy(task)

    assert strategy == "new_api_access_token"


def test_detect_site_strategy_for_sub2api_pending_reissue() -> None:
    task = _build_task(site_type="sub2api")

    strategy = detect_import_task_strategy(task)

    assert strategy == "sub2api_access_token"


def test_detect_site_strategy_returns_none_for_pending_import_task() -> None:
    task = _build_task(task_type="pending_import", site_type="anyrouter")

    strategy = detect_import_task_strategy(task)

    assert strategy is None


def test_detect_site_strategy_treats_unknown_access_token_as_probe_candidate() -> None:
    task = _build_task(site_type="unknown")

    strategy = detect_import_task_strategy(task)

    assert strategy == "probe_new_api_access_token"


@pytest.mark.asyncio
async def test_probe_new_api_compatibility_accepts_nested_data_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _request(**_kwargs: Any) -> dict[str, Any]:
        return {
            "success": True,
            "data": {
                "data": [
                    {"id": 1, "name": "zbs", "key": "sk-1"},
                ],
                "page": 1,
                "size": 5,
                "total_count": 1,
            },
        }

    monkeypatch.setattr(
        "src.services.provider_import.reissue._new_api_request",
        _request,
    )

    result = await _probe_new_api_compatibility(task=_build_task(site_type="unknown"))

    assert result is True


@pytest.mark.asyncio
async def test_find_new_api_token_accepts_nested_data_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _request(**_kwargs: Any) -> dict[str, Any]:
        return {
            "success": True,
            "data": {
                "data": [
                    {"id": 1, "name": "aether-acct-1", "key": "sk-1"},
                ],
                "page": 1,
                "size": 5,
                "total_count": 1,
            },
        }

    monkeypatch.setattr(
        "src.services.provider_import.reissue._new_api_request",
        _request,
    )

    token = await _find_new_api_token(
        base_url="https://provider-1.example.com",
        access_token="access-1",
        account_id="user-1",
        token_name="aether-acct-1",
    )

    assert token is not None
    assert token["key"] == "sk-1"


@pytest.mark.asyncio
async def test_execute_pending_reissue_creates_provider_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_reissue_new_api_key(*, task: ProviderImportTask) -> dict[str, str]:
        assert task.id == "task-1"
        return {
            "token_name": "aether-acct-1",
            "token_id": "upstream-token-1",
            "api_key": "sk-reissued-1",
        }

    async def _noop_side_effects(**_kwargs: Any) -> None:
        return None

    async def _verify(_key_id: str) -> str:
        return "success"

    monkeypatch.setattr(
        "src.services.provider_import.reissue._reissue_new_api_key",
        _fake_reissue_new_api_key,
    )
    monkeypatch.setattr(
        "src.services.provider_import.reissue.run_create_key_side_effects",
        _noop_side_effects,
    )
    monkeypatch.setattr(
        "src.services.provider_import.reissue._verify_reissued_key_models",
        _verify,
    )

    db = _FakeDB(
        providers=[
            Provider(
                id="provider-1",
                name="Provider One",
                provider_type="custom",
                billing_type="pay_as_you_go",
            )
        ],
        endpoints=[
            ProviderEndpoint(
                id="endpoint-1",
                provider_id="provider-1",
                api_format="openai:chat",
                api_family="openai",
                endpoint_kind="chat",
                base_url="https://provider-1.example.com",
            )
        ],
        tasks=[_build_task()],
    )

    result = await execute_all_in_hub_import_tasks(db=db, limit=10)

    assert result.total_selected == 1
    assert result.completed == 1
    assert result.failed == 0
    assert result.keys_created == 1
    assert len(db.keys) == 1
    assert db.keys[0].auto_fetch_models is True
    assert crypto_service.decrypt(db.keys[0].api_key) == "sk-reissued-1"
    assert db.tasks[0].status == "completed"
    assert db.tasks[0].source_metadata["result_token_id"] == "upstream-token-1"


@pytest.mark.asyncio
async def test_execute_import_task_is_idempotent_and_records_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _raise(*, task: ProviderImportTask) -> dict[str, str]:
        raise RuntimeError(f"boom:{task.id}")

    async def _noop_side_effects(**_kwargs: Any) -> None:
        return None

    async def _verify(_key_id: str) -> str:
        return "success"

    existing_key = ProviderAPIKey(
        id="key-1",
        provider_id="provider-1",
        api_formats=["openai:chat"],
        auth_type="api_key",
        api_key=crypto_service.encrypt("sk-reissued-1"),
        name="aether-acct-1",
        note="Reissued from all-in-hub task task-1",
        auto_fetch_models=True,
        is_active=True,
    )

    success_task = _build_task(status="completed")
    success_task.source_metadata["result_key_id"] = "key-1"

    failed_task = _build_task(task_id="task-2", source_id="acct-2")

    monkeypatch.setattr(
        "src.services.provider_import.reissue._reissue_new_api_key",
        _raise,
    )
    monkeypatch.setattr(
        "src.services.provider_import.reissue.run_create_key_side_effects",
        _noop_side_effects,
    )
    monkeypatch.setattr(
        "src.services.provider_import.reissue._verify_reissued_key_models",
        _verify,
    )

    db = _FakeDB(
        providers=[
            Provider(
                id="provider-1",
                name="Provider One",
                provider_type="custom",
                billing_type="pay_as_you_go",
            )
        ],
        endpoints=[
            ProviderEndpoint(
                id="endpoint-1",
                provider_id="provider-1",
                api_format="openai:chat",
                api_family="openai",
                endpoint_kind="chat",
                base_url="https://provider-1.example.com",
            )
        ],
        keys=[existing_key],
        tasks=[success_task, failed_task],
    )

    result = await execute_all_in_hub_import_tasks(db=db, limit=10)

    assert result.total_selected == 1
    assert result.completed == 0
    assert result.failed == 1
    assert result.keys_created == 0
    assert len(db.keys) == 1
    assert success_task.status == "completed"
    assert failed_task.status == "failed"
    assert failed_task.last_error == "boom:task-2"


@pytest.mark.asyncio
async def test_execute_pending_reissue_marks_task_failed_when_model_verification_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_reissue_new_api_key(*, task: ProviderImportTask) -> dict[str, str]:
        return {
            "token_name": "aether-acct-1",
            "token_id": "upstream-token-1",
            "api_key": "sk-reissued-1",
        }

    async def _noop_side_effects(**_kwargs: Any) -> None:
        return None

    async def _fake_verify(_key_id: str) -> str:
        return "error"

    monkeypatch.setattr(
        "src.services.provider_import.reissue._reissue_new_api_key",
        _fake_reissue_new_api_key,
    )
    monkeypatch.setattr(
        "src.services.provider_import.reissue.run_create_key_side_effects",
        _noop_side_effects,
    )
    monkeypatch.setattr(
        "src.services.provider_import.reissue._verify_reissued_key_models",
        _fake_verify,
    )

    db = _FakeDB(
        providers=[
            Provider(
                id="provider-1",
                name="Provider One",
                provider_type="custom",
                billing_type="pay_as_you_go",
            )
        ],
        endpoints=[
            ProviderEndpoint(
                id="endpoint-1",
                provider_id="provider-1",
                api_format="openai:chat",
                api_family="openai",
                endpoint_kind="chat",
                base_url="https://provider-1.example.com",
            )
        ],
        tasks=[_build_task()],
    )

    result = await execute_all_in_hub_import_tasks(db=db, limit=10)

    assert result.completed == 0
    assert result.failed == 1
    assert result.keys_created == 1
    assert len(db.keys) == 1
    assert db.keys[0].is_active is False
    assert db.tasks[0].status == "failed"
    assert "model verification failed" in str(db.tasks[0].last_error)
    assert result.results[0]["stage"] == "verify_models"
    assert result.results[0]["key_created"] is True
    assert result.results[0]["result_key_id"] == str(db.keys[0].id)


@pytest.mark.asyncio
async def test_execute_sub2api_pending_reissue_reports_expired_access_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _probe(*, task: ProviderImportTask) -> None:
        raise RuntimeError("sub2api access token expired")

    db = _FakeDB(
        providers=[
            Provider(
                id="provider-1",
                name="Provider One",
                provider_type="custom",
                billing_type="pay_as_you_go",
            )
        ],
        endpoints=[
            ProviderEndpoint(
                id="endpoint-1",
                provider_id="provider-1",
                api_format="openai:chat",
                api_family="openai",
                endpoint_kind="chat",
                base_url="https://provider-1.example.com",
            )
        ],
        tasks=[_build_task(site_type="sub2api")],
    )

    monkeypatch.setattr(
        "src.services.provider_import.reissue._probe_sub2api_access_token",
        _probe,
    )

    result = await execute_all_in_hub_import_tasks(db=db, limit=10)

    assert result.completed == 0
    assert result.failed == 1
    assert result.keys_created == 0
    assert db.tasks[0].status == "failed"
    assert db.tasks[0].last_error == "sub2api access token expired"


@pytest.mark.asyncio
async def test_execute_pending_import_task_is_not_selected_for_execution() -> None:
    task = _build_task(task_type="pending_import", site_type="anyrouter")

    db = _FakeDB(
        providers=[
            Provider(
                id="provider-1",
                name="Provider One",
                provider_type="custom",
                billing_type="pay_as_you_go",
            )
        ],
        endpoints=[
            ProviderEndpoint(
                id="endpoint-1",
                provider_id="provider-1",
                api_format="openai:chat",
                api_family="openai",
                endpoint_kind="chat",
                base_url="https://provider-1.example.com",
            )
        ],
        tasks=[task],
    )

    result = await execute_all_in_hub_import_tasks(db=db, limit=10)

    assert result.total_selected == 0
    assert result.completed == 0
    assert result.failed == 0
    assert result.skipped == 0
    assert result.keys_created == 0
    assert task.status == "pending"
    assert task.last_error is None


@pytest.mark.asyncio
async def test_execute_import_tasks_selects_only_pending_reissue_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_reissue_new_api_key(*, task: ProviderImportTask) -> dict[str, str]:
        assert task.id == "task-reissue"
        return {
            "token_name": "aether-acct-1",
            "token_id": "upstream-token-1",
            "api_key": "sk-reissued-selected-only",
        }

    async def _noop_side_effects(**_kwargs: Any) -> None:
        return None

    async def _verify(_key_id: str) -> str:
        return "success"

    monkeypatch.setattr(
        "src.services.provider_import.reissue._reissue_new_api_key",
        _fake_reissue_new_api_key,
    )
    monkeypatch.setattr(
        "src.services.provider_import.reissue.run_create_key_side_effects",
        _noop_side_effects,
    )
    monkeypatch.setattr(
        "src.services.provider_import.reissue._verify_reissued_key_models",
        _verify,
    )

    pending_reissue = _build_task(task_id="task-reissue", task_type="pending_reissue", status="pending")
    pending_import = _build_task(task_id="task-import", task_type="pending_import", site_type="anyrouter", status="pending")
    completed_task = _build_task(task_id="task-completed", task_type="pending_reissue", status="completed")
    failed_task = _build_task(task_id="task-failed", task_type="pending_reissue", status="failed")

    db = _FakeDB(
        providers=[
            Provider(
                id="provider-1",
                name="Provider One",
                provider_type="custom",
                billing_type="pay_as_you_go",
            )
        ],
        endpoints=[
            ProviderEndpoint(
                id="endpoint-1",
                provider_id="provider-1",
                api_format="openai:chat",
                api_family="openai",
                endpoint_kind="chat",
                base_url="https://provider-1.example.com",
            )
        ],
        tasks=[pending_import, completed_task, failed_task, pending_reissue],
    )

    result = await execute_all_in_hub_import_tasks(db=db, limit=10)

    assert result.total_selected == 1
    assert result.skipped == 0
    assert result.completed == 1
    assert result.failed == 0
    assert pending_import.status == "pending"
    assert completed_task.status == "completed"
    assert failed_task.status == "failed"


@pytest.mark.asyncio
async def test_execute_unknown_pending_reissue_falls_back_to_new_api_when_probe_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _probe(*, task: ProviderImportTask) -> bool:
        assert task.source_metadata["site_type"] == "unknown"
        return True

    async def _fake_reissue_new_api_key(*, task: ProviderImportTask) -> dict[str, str]:
        return {
            "token_name": "aether-acct-1",
            "token_id": "upstream-token-1",
            "api_key": "sk-reissued-unknown-1",
        }

    async def _noop_side_effects(**_kwargs: Any) -> None:
        return None

    async def _verify(_key_id: str) -> str:
        return "success"

    monkeypatch.setattr(
        "src.services.provider_import.reissue._probe_new_api_compatibility",
        _probe,
    )
    monkeypatch.setattr(
        "src.services.provider_import.reissue._reissue_new_api_key",
        _fake_reissue_new_api_key,
    )
    monkeypatch.setattr(
        "src.services.provider_import.reissue.run_create_key_side_effects",
        _noop_side_effects,
    )
    monkeypatch.setattr(
        "src.services.provider_import.reissue._verify_reissued_key_models",
        _verify,
    )

    db = _FakeDB(
        providers=[
            Provider(
                id="provider-1",
                name="Provider One",
                provider_type="custom",
                billing_type="pay_as_you_go",
            )
        ],
        endpoints=[
            ProviderEndpoint(
                id="endpoint-1",
                provider_id="provider-1",
                api_format="openai:chat",
                api_family="openai",
                endpoint_kind="chat",
                base_url="https://provider-1.example.com",
            )
        ],
        tasks=[_build_task(site_type="unknown")],
    )

    result = await execute_all_in_hub_import_tasks(db=db, limit=10)

    assert result.completed == 1
    assert result.failed == 0
    assert result.keys_created == 1
    assert db.tasks[0].status == "completed"
    assert crypto_service.decrypt(db.keys[0].api_key) == "sk-reissued-unknown-1"


@pytest.mark.asyncio
async def test_execute_unknown_pending_reissue_fails_when_probe_rejects_new_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _probe(*, task: ProviderImportTask) -> bool:
        assert task.source_metadata["site_type"] == "unknown"
        return False

    db = _FakeDB(
        providers=[
            Provider(
                id="provider-1",
                name="Provider One",
                provider_type="custom",
                billing_type="pay_as_you_go",
            )
        ],
        endpoints=[
            ProviderEndpoint(
                id="endpoint-1",
                provider_id="provider-1",
                api_format="openai:chat",
                api_family="openai",
                endpoint_kind="chat",
                base_url="https://provider-1.example.com",
            )
        ],
        tasks=[_build_task(site_type="unknown")],
    )

    monkeypatch.setattr(
        "src.services.provider_import.reissue._probe_new_api_compatibility",
        _probe,
    )

    result = await execute_all_in_hub_import_tasks(db=db, limit=10)

    assert result.completed == 0
    assert result.failed == 1
    assert result.keys_created == 0
    assert db.tasks[0].status == "failed"
    assert db.tasks[0].last_error == "unknown site is not compatible with new-api reissue"
