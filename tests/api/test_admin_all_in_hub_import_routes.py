from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.admin.providers import router as providers_router
from src.api.admin.providers.routes import get_db
from src.models.provider_import import (
    AllInHubImportProviderSummary,
    AllInHubImportResponse,
    AllInHubImportStats,
    AllInHubTaskExecutionResponse,
)


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
            },
            {
                "task_id": "task-2",
                "status": "failed",
                "stage": "verify_models",
                "last_error": "boom:task-2",
                "key_created": True,
                "result_key_id": None,
            },
        ],
    )


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
    import_mock.assert_awaited_once()


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
    execute_mock.assert_awaited_once()
