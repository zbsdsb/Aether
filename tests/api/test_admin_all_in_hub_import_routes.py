from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.admin.providers import router as providers_router
from src.api.admin.providers.routes import get_db
from src.models.provider_import import (
    AllInHubImportBackgroundTaskStatus,
    AllInHubImportJobListResponse,
    AllInHubImportProviderIssue,
    AllInHubImportJobStatusResponse,
    AllInHubImportProviderSummary,
    AllInHubImportResponse,
    AllInHubImportManualItem,
    AllInHubImportStats,
    AllInHubTaskExecutionResponse,
)
from src.services.provider_import.reissue import PlaintextSubmissionRetryableError


def _build_app(db: object, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app = FastAPI()
    app.include_router(providers_router)
    app.dependency_overrides[get_db] = lambda: db

    async def _fake_pipeline_run(adapter, http_request, db, mode=None):  # type: ignore[no-untyped-def]
        _ = mode
        context = SimpleNamespace(
            db=db,
            request=http_request,
            user=SimpleNamespace(id="admin-1", username="admin-1"),
            add_audit_metadata=lambda **_kwargs: None,
        )
        return await adapter.handle(context)

    monkeypatch.setattr("src.api.admin.providers.routes.pipeline.run", _fake_pipeline_run)
    return TestClient(app)


def _response_payload(dry_run: bool) -> AllInHubImportResponse:
    return AllInHubImportResponse(
        dry_run=dry_run,
        version="2.0",
        stats=AllInHubImportStats(
            providers_total=1,
            providers_to_create=1 if dry_run else 0,
            providers_created=0 if dry_run else 1,
            providers_reused=0,
            endpoints_to_create=1 if dry_run else 0,
            endpoints_created=0 if dry_run else 1,
            endpoints_reused=0,
            direct_keys_ready=1,
            pending_sources=1,
            pending_tasks_to_create=1 if dry_run else 0,
            pending_tasks_created=0 if dry_run else 1,
            pending_tasks_reused=0,
            keys_created=0 if dry_run else 1,
            keys_skipped=0,
        ),
        warnings=["pending source requires manual completion"],
        providers=[
            AllInHubImportProviderSummary(
                provider_name="Provider One",
                provider_website="https://provider-1.example.com",
                endpoint_base_url="https://provider-1.example.com/v1",
                direct_key_count=1,
                pending_source_count=1,
                existing_provider=False,
                existing_endpoint=False,
            )
        ],
        manual_items=[
            AllInHubImportManualItem(
                item_type="pending_task",
                status="pending",
                provider_name="Provider One",
                provider_website="https://provider-1.example.com",
                endpoint_base_url="https://provider-1.example.com/v1",
                source_id="acct-1",
                task_type="pending_reissue",
                auth_type="access_token",
                site_type="new-api",
                reason="缺少明文 Key，等待人工补抓或补录",
            ),
            AllInHubImportManualItem(
                item_type="verification_failure",
                status="failed",
                provider_name="Provider Two",
                provider_website="https://provider-2.example.com",
                endpoint_base_url="https://provider-2.example.com/v1",
                source_id="acct-2",
                task_type=None,
                auth_type="api_key",
                site_type="new-api",
                reason="/v1/models 返回空列表，等待人工复核",
            ),
        ],
    )


def _task_execution_payload() -> AllInHubTaskExecutionResponse:
    return AllInHubTaskExecutionResponse(
        total_selected=2,
        completed=1,
        failed=1,
        skipped=0,
        keys_created=1,
        results=[
            {
                "task_id": "task-1",
                "status": "completed",
                "stage": "completed",
                "last_error": None,
                "key_created": True,
                "result_key_id": "key-1",
                "task_type": "pending_reissue",
                "site_type": "new-api",
                "auth_type": "access_token",
                "has_access_token": True,
                "has_session_cookie": False,
                "action_required": None,
                "plaintext_capture_status": "consumed",
                "masked_key_preview": None,
            },
            {
                "task_id": "task-2",
                "status": "waiting_plaintext",
                "stage": "create_key",
                "last_error": None,
                "key_created": False,
                "result_key_id": None,
                "task_type": "pending_import",
                "site_type": "anyrouter",
                "auth_type": "cookie",
                "has_access_token": True,
                "has_session_cookie": True,
                "action_required": "submit_plaintext",
                "plaintext_capture_status": "pending",
                "masked_key_preview": "xBLk**********d1O9",
            },
        ],
    )


def _submit_plaintext_payload() -> dict[str, object]:
    return {
        "task_id": "task-2",
        "status": "completed",
        "stage": "completed",
        "last_error": None,
        "key_created": True,
        "result_key_id": "key-2",
        "task_type": "pending_reissue",
        "site_type": "new-api",
        "auth_type": "access_token",
        "has_access_token": True,
        "has_session_cookie": False,
        "action_required": None,
        "plaintext_capture_status": "consumed",
        "masked_key_preview": "xBLk**********d1O9",
    }


def test_preview_all_in_hub_import_route_returns_service_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preview_mock = AsyncMock(return_value=_response_payload(dry_run=True))
    monkeypatch.setattr("src.api.admin.providers.routes.preview_all_in_hub_import", preview_mock)

    client = _build_app(object(), monkeypatch)
    response = client.post(
        "/api/admin/providers/imports/all-in-hub/preview",
        json={"content": "{\"version\":\"2.0\"}"},
    )

    assert response.status_code == 200
    assert response.json()["dry_run"] is True
    assert response.json()["stats"]["direct_keys_ready"] == 1
    assert response.json()["manual_items"][0]["item_type"] == "pending_task"
    preview_mock.assert_awaited_once()


def test_import_all_in_hub_route_returns_service_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import_mock = AsyncMock(return_value=_response_payload(dry_run=False))
    monkeypatch.setattr("src.api.admin.providers.routes.execute_all_in_hub_import", import_mock)

    client = _build_app(object(), monkeypatch)
    response = client.post(
        "/api/admin/providers/imports/all-in-hub",
        json={"content": "{\"version\":\"2.0\"}"},
    )

    assert response.status_code == 200
    assert response.json()["dry_run"] is False
    assert response.json()["stats"]["keys_created"] == 1
    assert response.json()["manual_items"][1]["status"] == "failed"
    import_mock.assert_awaited_once()


def test_submit_all_in_hub_import_route_returns_job_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submit_mock = AsyncMock(return_value="job-1")
    monkeypatch.setattr(
        "src.api.admin.providers.routes.submit_all_in_hub_import_job",
        submit_mock,
    )

    client = _build_app(object(), monkeypatch)
    response = client.post(
        "/api/admin/providers/imports/all-in-hub/submit",
        json={"content": "{\"version\":\"2.0\"}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "task_id": "job-1",
        "status": "pending",
        "stage": "queued",
        "message": "导入任务已提交，后台处理中",
    }
    submit_mock.assert_awaited_once()


def test_get_all_in_hub_import_task_route_returns_job_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_mock = AsyncMock(
        return_value=AllInHubImportJobStatusResponse(
            task_id="job-1",
            status="running",
            stage="executing_tasks",
            message="execution round 1",
            created_at="2026-04-08T06:00:00+00:00",
            updated_at="2026-04-08T06:01:00+00:00",
            background_tasks=[
                AllInHubImportBackgroundTaskStatus(
                    key="fetch_models",
                    label="异步抓取上游模型",
                    status="running",
                    total=2,
                    completed=1,
                    failed=0,
                    message="正在抓取第 2/2 个 Key",
                ),
                AllInHubImportBackgroundTaskStatus(
                    key="proxy_probe",
                    label="代理检测",
                    status="pending",
                    total=1,
                    completed=0,
                    failed=0,
                    message="等待模型抓取结束后执行",
                ),
            ],
            provider_issues=[
                AllInHubImportProviderIssue(
                    provider_id="provider-1",
                    provider_name="Anyrouter",
                    status="failed",
                    mode="system_proxy",
                    message="invalid refresh token",
                )
            ],
            import_result=_response_payload(dry_run=False),
            execution_result=_task_execution_payload(),
        )
    )
    monkeypatch.setattr(
        "src.api.admin.providers.routes.get_all_in_hub_import_job",
        get_mock,
    )

    client = _build_app(object(), monkeypatch)
    response = client.get("/api/admin/providers/imports/all-in-hub/tasks/job-1")

    assert response.status_code == 200
    assert response.json()["task_id"] == "job-1"
    assert response.json()["status"] == "running"
    assert response.json()["execution_result"]["total_selected"] == 2
    assert response.json()["background_tasks"][0]["key"] == "fetch_models"
    assert response.json()["background_tasks"][1]["status"] == "pending"
    assert response.json()["provider_issues"][0]["provider_name"] == "Anyrouter"
    get_mock.assert_awaited_once()


def test_list_all_in_hub_import_tasks_route_returns_recent_jobs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    list_mock = AsyncMock(
        return_value=AllInHubImportJobListResponse(
            items=[
                AllInHubImportJobStatusResponse(
                    task_id="job-1",
                    status="completed",
                    stage="completed",
                    message="done",
                    created_at="2026-04-08T06:00:00+00:00",
                    updated_at="2026-04-08T06:05:00+00:00",
                    background_tasks=[],
                    provider_issues=[],
                    import_result=_response_payload(dry_run=False),
                    execution_result=_task_execution_payload(),
                )
            ],
            total=1,
        )
    )
    monkeypatch.setattr(
        "src.api.admin.providers.routes.list_all_in_hub_import_jobs",
        list_mock,
    )

    client = _build_app(object(), monkeypatch)
    response = client.get("/api/admin/providers/imports/all-in-hub/tasks?limit=10")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["task_id"] == "job-1"
    assert response.json()["items"][0]["created_at"] == "2026-04-08T06:00:00+00:00"
    list_mock.assert_awaited_once()


def test_execute_all_in_hub_pending_tasks_route_returns_service_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execute_mock = AsyncMock(return_value=_task_execution_payload())
    monkeypatch.setattr(
        "src.api.admin.providers.routes.execute_all_in_hub_import_tasks",
        execute_mock,
    )

    client = _build_app(object(), monkeypatch)
    response = client.post(
        "/api/admin/providers/imports/all-in-hub/tasks/execute",
        json={"limit": 5},
    )

    assert response.status_code == 200
    assert response.json()["total_selected"] == 2
    assert response.json()["keys_created"] == 1
    assert response.json()["results"][0]["site_type"] == "new-api"
    assert response.json()["results"][1]["auth_type"] == "cookie"
    assert response.json()["results"][1]["action_required"] == "submit_plaintext"
    assert response.json()["results"][1]["plaintext_capture_status"] == "pending"
    execute_mock.assert_awaited_once()


def test_submit_all_in_hub_task_plaintext_route_returns_service_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submit_mock = AsyncMock(return_value=_submit_plaintext_payload())
    monkeypatch.setattr(
        "src.api.admin.providers.routes.submit_all_in_hub_task_plaintext",
        submit_mock,
    )

    client = _build_app(object(), monkeypatch)
    response = client.post(
        "/api/admin/providers/imports/all-in-hub/tasks/task-2/submit-plaintext",
        json={
            "api_key": "sk-captured-1",
            "token_name": "aether-acct-1",
            "token_id": "upstream-token-1",
            "note": "captured via browser",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["result_key_id"] == "key-2"
    submit_mock.assert_awaited_once()


def test_submit_all_in_hub_task_plaintext_route_maps_retryable_failure_to_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _raise_conflict(**_kwargs: object) -> dict[str, object]:
        raise PlaintextSubmissionRetryableError("model verification failed: error")

    monkeypatch.setattr(
        "src.api.admin.providers.routes.submit_all_in_hub_task_plaintext",
        _raise_conflict,
    )

    client = _build_app(object(), monkeypatch)
    response = client.post(
        "/api/admin/providers/imports/all-in-hub/tasks/task-2/submit-plaintext",
        json={
            "api_key": "sk-captured-1",
            "token_name": "aether-acct-1",
            "token_id": "upstream-token-1",
            "note": "captured via browser",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "model verification failed: error"
