from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from src.core.crypto import crypto_service
from src.models.database import Provider, ProviderAPIKey, ProviderEndpoint, ProviderImportTask
from src.api.admin.providers.summary import _summarize_provider_import_tasks
from src.services.provider_import.reissue import (
    _create_new_api_token,
    detect_import_task_strategy,
    _find_new_api_token,
    _probe_new_api_compatibility,
    execute_all_in_hub_import_tasks,
    submit_all_in_hub_task_plaintext,
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
    refresh_token: str | None = None,
    session_cookie: str | None = None,
    account_id: str | None = "user-1",
    source_id: str = "acct-1",
    status: str = "pending",
) -> ProviderImportTask:
    payload = crypto_service.encrypt(
        '{"access_token": %s, "refresh_token": %s, "session_cookie": %s}'
        % (
            f'"{access_token}"' if access_token is not None else "null",
            f'"{refresh_token}"' if refresh_token is not None else "null",
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
            "auth_type": "cookie" if session_cookie else ("access_token" if access_token else None),
            "account_id": account_id,
            "endpoint_base_url": "https://provider-1.example.com",
            "provider_name": "Provider One",
            "has_access_token": bool(access_token),
            "has_refresh_token": bool(refresh_token),
            "has_session_cookie": bool(session_cookie),
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
async def test_create_new_api_token_uses_string_model_limits_for_real_new_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def _request(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"success": True, "data": {"id": 1}}

    monkeypatch.setattr(
        "src.services.provider_import.reissue._new_api_request",
        _request,
    )

    await _create_new_api_token(
        base_url="https://provider-1.example.com",
        access_token="access-1",
        account_id="user-1",
        token_name="aether-acct-1",
    )

    assert captured["json_body"]["model_limits"] == ""


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
    assert result.results[0]["task_type"] == "pending_reissue"
    assert result.results[0]["site_type"] == "new-api"
    assert result.results[0]["has_access_token"] is True
    assert result.results[0]["has_session_cookie"] is False


@pytest.mark.asyncio
async def test_execute_new_api_pending_reissue_rejects_masked_token_list_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_new_api_request(
        *,
        method: str,
        base_url: str,
        access_token: str,
        account_id: str,
        path: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert base_url == "https://provider-1.example.com"
        assert access_token == "access-1"
        assert account_id == "acct-1"
        if method == "GET":
            return {
                "success": True,
                "data": {
                    "items": [
                        {
                            "id": 1,
                            "name": "aether-acct-1",
                            "key": "xBLk**********d1O9",
                        }
                    ],
                    "total": 1,
                },
            }
        raise AssertionError(f"unexpected request: {(method, path, json_body)}")

    async def _unexpected_side_effects(**_kwargs: Any) -> None:
        raise AssertionError("masked key should fail before side effects")

    async def _unexpected_verify(_key_id: str) -> str:
        raise AssertionError("masked key should fail before verify")

    monkeypatch.setattr(
        "src.services.provider_import.reissue._new_api_request",
        _fake_new_api_request,
    )
    monkeypatch.setattr(
        "src.services.provider_import.reissue.run_create_key_side_effects",
        _unexpected_side_effects,
    )
    monkeypatch.setattr(
        "src.services.provider_import.reissue._verify_reissued_key_models",
        _unexpected_verify,
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
        tasks=[_build_task(account_id="acct-1")],
    )

    result = await execute_all_in_hub_import_tasks(db=db, limit=10)

    assert result.total_selected == 1
    assert result.completed == 0
    assert result.failed == 0
    assert result.keys_created == 0
    assert len(db.keys) == 0
    assert db.tasks[0].status == "waiting_plaintext"
    assert db.tasks[0].last_error is None
    assert db.tasks[0].source_metadata["plaintext_capture_status"] == "pending"
    assert db.tasks[0].source_metadata["action_required"] == "submit_plaintext"
    assert db.tasks[0].source_metadata["masked_key_preview"] == "xBLk**********d1O9"
    assert result.results[0]["stage"] == "create_key"
    assert result.results[0]["key_created"] is False
    assert result.results[0]["action_required"] == "submit_plaintext"
    assert result.results[0]["plaintext_capture_status"] == "pending"
    assert result.results[0]["masked_key_preview"] == "xBLk**********d1O9"


@pytest.mark.asyncio
async def test_submit_plaintext_creates_provider_api_key_and_completes_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _noop_side_effects(**_kwargs: Any) -> None:
        return None

    async def _verify(_key_id: str) -> str:
        return "success"

    monkeypatch.setattr(
        "src.services.provider_import.reissue.run_create_key_side_effects",
        _noop_side_effects,
    )
    monkeypatch.setattr(
        "src.services.provider_import.reissue._verify_reissued_key_models",
        _verify,
    )

    task = _build_task(status="waiting_plaintext")
    task.source_metadata["plaintext_capture_status"] = "pending"
    task.source_metadata["action_required"] = "submit_plaintext"
    task.source_metadata["masked_key_preview"] = "xBLk**********d1O9"
    task.source_metadata["result_token_name"] = "aether-acct-1"
    task.source_metadata["result_token_id"] = "upstream-token-1"

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

    result = await submit_all_in_hub_task_plaintext(
        db=db,
        task_id="task-1",
        plaintext_api_key="sk-reissued-from-submit",
        token_name="aether-acct-1",
        token_id="upstream-token-1",
        note="captured via browser",
    )

    assert result["status"] == "completed"
    assert result["stage"] == "completed"
    assert result["key_created"] is True
    assert len(db.keys) == 1
    assert crypto_service.decrypt(db.keys[0].api_key) == "sk-reissued-from-submit"
    assert task.status == "completed"
    assert task.source_metadata["plaintext_capture_status"] == "consumed"
    assert task.source_metadata["result_key_id"] == str(db.keys[0].id)
    assert task.source_metadata["plaintext_submission_note"] == "captured via browser"


@pytest.mark.asyncio
async def test_submit_plaintext_accepts_legacy_waiting_plaintext_task_without_metadata_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _noop_side_effects(**_kwargs: Any) -> None:
        return None

    async def _verify(_key_id: str) -> str:
        return "success"

    monkeypatch.setattr(
        "src.services.provider_import.reissue.run_create_key_side_effects",
        _noop_side_effects,
    )
    monkeypatch.setattr(
        "src.services.provider_import.reissue._verify_reissued_key_models",
        _verify,
    )

    task = _build_task(status="waiting_plaintext")
    task.source_metadata.pop("plaintext_capture_status", None)
    task.source_metadata.pop("action_required", None)
    task.source_metadata["masked_key_preview"] = "sk-tq4v************Wy5"

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

    result = await submit_all_in_hub_task_plaintext(
        db=db,
        task_id="task-1",
        plaintext_api_key="sk-legacy-waiting-plaintext",
        note="captured via copy button",
    )

    assert result["status"] == "completed"
    assert result["key_created"] is True
    assert task.status == "completed"
    assert task.source_metadata["plaintext_capture_status"] == "consumed"
    assert task.source_metadata["action_required"] is None
    assert task.source_metadata["plaintext_submission_note"] == "captured via copy button"


@pytest.mark.asyncio
async def test_submit_plaintext_rejects_task_not_waiting_for_plaintext() -> None:
    task = _build_task(status="pending")
    db = _FakeDB(tasks=[task])

    with pytest.raises(RuntimeError, match="task is not waiting for plaintext submission"):
        await submit_all_in_hub_task_plaintext(
            db=db,
            task_id="task-1",
            plaintext_api_key="sk-reissued-from-submit",
        )


@pytest.mark.asyncio
async def test_submit_plaintext_keeps_task_retryable_when_model_verification_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _noop_side_effects(**_kwargs: Any) -> None:
        return None

    async def _verify(_key_id: str) -> str:
        return "error"

    monkeypatch.setattr(
        "src.services.provider_import.reissue.run_create_key_side_effects",
        _noop_side_effects,
    )
    monkeypatch.setattr(
        "src.services.provider_import.reissue._verify_reissued_key_models",
        _verify,
    )

    task = _build_task(status="waiting_plaintext")
    task.source_metadata["plaintext_capture_status"] = "pending"
    task.source_metadata["action_required"] = "submit_plaintext"
    task.source_metadata["masked_key_preview"] = "xBLk**********d1O9"

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

    with pytest.raises(RuntimeError, match="model verification failed: error"):
        await submit_all_in_hub_task_plaintext(
            db=db,
            task_id="task-1",
            plaintext_api_key="sk-invalid-or-unverified",
            token_name="manual-captured-token",
            token_id="manual-token-id",
            note="captured via browser",
        )

    assert len(db.keys) == 1
    assert db.keys[0].is_active is False
    assert task.status == "waiting_plaintext"
    assert task.last_error == "model verification failed: error"
    assert task.retry_count == 1
    assert task.source_metadata["plaintext_capture_status"] == "pending"
    assert task.source_metadata["action_required"] == "submit_plaintext"
    assert task.source_metadata["result_key_id"] == str(db.keys[0].id)


@pytest.mark.asyncio
async def test_submit_plaintext_reuses_inactive_existing_key_by_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _noop_side_effects(**_kwargs: Any) -> None:
        return None

    existing_key = ProviderAPIKey(
        id="key-existing",
        provider_id="provider-1",
        api_formats=["openai:chat"],
        auth_type="api_key",
        api_key=crypto_service.encrypt("sk-existing-retry"),
        name="aether-acct-1",
        note="Reissued from all-in-hub task task-1",
        auto_fetch_models=True,
        is_active=False,
    )

    async def _verify(key_id: str) -> str:
        assert key_id == "key-existing"
        assert existing_key.is_active is True
        return "success"

    monkeypatch.setattr(
        "src.services.provider_import.reissue.run_create_key_side_effects",
        _noop_side_effects,
    )
    monkeypatch.setattr(
        "src.services.provider_import.reissue._verify_reissued_key_models",
        _verify,
    )

    task = _build_task(status="waiting_plaintext")
    task.source_metadata["plaintext_capture_status"] = "pending"
    task.source_metadata["action_required"] = "submit_plaintext"
    task.source_metadata["result_key_id"] = "key-existing"

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
        tasks=[task],
    )

    result = await submit_all_in_hub_task_plaintext(
        db=db,
        task_id="task-1",
        plaintext_api_key="sk-existing-retry",
        note="retry existing key",
    )

    assert result["status"] == "completed"
    assert result["key_created"] is False
    assert len(db.keys) == 1
    assert existing_key.is_active is True
    assert task.status == "completed"
    assert task.source_metadata["result_key_id"] == "key-existing"
    assert task.source_metadata["plaintext_submission_note"] == "retry existing key"


@pytest.mark.asyncio
async def test_submit_plaintext_resolves_same_source_failed_sibling_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _noop_side_effects(**_kwargs: Any) -> None:
        return None

    async def _verify(_key_id: str) -> str:
        return "success"

    monkeypatch.setattr(
        "src.services.provider_import.reissue.run_create_key_side_effects",
        _noop_side_effects,
    )
    monkeypatch.setattr(
        "src.services.provider_import.reissue._verify_reissued_key_models",
        _verify,
    )

    task = _build_task(task_id="task-current", status="waiting_plaintext", source_id="acct-shared")
    task.source_metadata["plaintext_capture_status"] = "pending"
    task.source_metadata["action_required"] = "submit_plaintext"
    task.source_metadata["masked_key_preview"] = "xBLk**********d1O9"

    sibling_failed = _build_task(
        task_id="task-failed",
        status="failed",
        source_id="acct-shared",
    )
    sibling_failed.last_error = "model verification failed: timeout"
    sibling_failed.source_metadata["action_required"] = "submit_plaintext"
    sibling_failed.source_metadata["plaintext_capture_status"] = "pending"

    unrelated_failed = _build_task(
        task_id="task-other",
        status="failed",
        source_id="acct-other",
    )
    unrelated_failed.last_error = "still broken"

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
        tasks=[task, sibling_failed, unrelated_failed],
    )

    before_summary = _summarize_provider_import_tasks(db.tasks)
    assert before_summary.import_task_failed == 2
    assert before_summary.needs_manual_review is True

    result = await submit_all_in_hub_task_plaintext(
        db=db,
        task_id="task-current",
        plaintext_api_key="sk-reissued-from-submit",
        note="captured via browser",
    )

    assert result["status"] == "completed"
    assert task.status == "completed"
    assert sibling_failed.status == "completed"
    assert sibling_failed.last_error is None
    assert sibling_failed.source_metadata["plaintext_capture_status"] == "consumed"
    assert sibling_failed.source_metadata["action_required"] is None
    assert unrelated_failed.status == "failed"

    after_summary = _summarize_provider_import_tasks(db.tasks)
    assert after_summary.import_task_waiting_plaintext == 0
    assert after_summary.import_task_failed == 1
    assert after_summary.needs_manual_key_input is False
    assert after_summary.needs_manual_review is True


@pytest.mark.asyncio
async def test_execute_sub2api_pending_reissue_creates_provider_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _noop_probe(*, task: ProviderImportTask) -> None:
        assert task.id == "task-1"
        return None

    calls: list[tuple[str, str]] = []

    async def _fake_sub2api_request(
        *,
        method: str,
        base_url: str,
        access_token: str,
        path: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert base_url == "https://provider-1.example.com"
        assert access_token == "access-1"
        calls.append((method, path))
        if method == "GET" and path.startswith("api/v1/keys") and len(calls) == 1:
            return {"code": 0, "message": "ok", "data": {"items": []}}
        if method == "POST" and path == "api/v1/keys":
            assert json_body == {"name": "aether-acct-1"}
            return {"code": 0, "message": "ok", "data": {"id": 1}}
        if method == "GET" and path.startswith("api/v1/keys"):
            return {
                "code": 0,
                "message": "ok",
                "data": {
                    "items": [
                        {"id": 1, "name": "aether-acct-1", "key": "sk-sub2api-reissued-1"}
                    ]
                },
            }
        raise AssertionError(f"unexpected sub2api request: {(method, path, json_body)}")

    async def _noop_side_effects(**_kwargs: Any) -> None:
        return None

    async def _verify(_key_id: str) -> str:
        return "success"

    monkeypatch.setattr(
        "src.services.provider_import.reissue._probe_sub2api_access_token",
        _noop_probe,
    )
    monkeypatch.setattr(
        "src.services.provider_import.reissue._sub2api_request",
        _fake_sub2api_request,
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
        tasks=[_build_task(site_type="sub2api")],
    )

    result = await execute_all_in_hub_import_tasks(db=db, limit=10)

    assert result.total_selected == 1
    assert result.completed == 1
    assert result.failed == 0
    assert result.keys_created == 1
    assert len(db.keys) == 1
    assert crypto_service.decrypt(db.keys[0].api_key) == "sk-sub2api-reissued-1"
    assert db.tasks[0].status == "completed"
    assert db.tasks[0].source_metadata["result_token_id"] == "1"
    assert result.results[0]["task_type"] == "pending_reissue"
    assert result.results[0]["site_type"] == "sub2api"
    assert result.results[0]["has_access_token"] is True


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
    assert result.results[0]["provider_name"] == "Provider One"
    assert result.results[0]["provider_website"] == "https://provider-1.example.com"
    assert result.results[0]["endpoint_base_url"] == "https://provider-1.example.com"
    assert result.results[0]["source_id"] == "acct-1"
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


@pytest.mark.asyncio
async def test_execute_imported_auth_prefill_auto_configures_sub2api_without_running_proxy_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = Provider(
        id="provider-1",
        name="Provider One",
        provider_type="custom",
        billing_type="pay_as_you_go",
        website="https://provider-1.example.com",
    )
    endpoint = ProviderEndpoint(
        id="endpoint-1",
        provider_id="provider-1",
        api_format="openai:chat",
        api_family="openai",
        endpoint_kind="chat",
        base_url="https://provider-1.example.com",
    )
    task = _build_task(
        task_type="imported_auth_prefill",
        site_type="sub2api",
        access_token="access-1",
        refresh_token="rt-1",
    )
    db = _FakeDB(providers=[provider], endpoints=[endpoint], tasks=[task])

    result = await execute_all_in_hub_import_tasks(db=db, limit=10)

    assert result.total_selected == 1
    assert result.completed == 1
    assert result.results[0]["status"] == "completed"
    assert result.results[0]["stage"] == "auth_config"
    assert task.status == "completed"
    assert provider.config is not None

    provider_ops = provider.config["provider_ops"]
    assert provider_ops["architecture_id"] == "sub2api"
    assert provider_ops["connector"]["auth_type"] == "api_key"
    assert provider_ops["connector"]["config"] == {}
    assert crypto_service.decrypt(provider_ops["connector"]["credentials"]["refresh_token"]) == "rt-1"
    assert provider_ops["_auto_imported"] is True
    assert task.source_metadata["auto_proxy_probe_status"] == "pending"
