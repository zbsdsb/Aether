from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.admin.async_tasks.routes import router as async_tasks_router
from src.database.database import get_db
from src.utils.auth_utils import get_current_user


def _build_app(db: object) -> TestClient:
    app = FastAPI()
    app.include_router(async_tasks_router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="admin-1",
        username="admin",
        role="admin",
    )
    return TestClient(app)


def test_list_admin_async_tasks_route_returns_aggregated_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    list_mock = AsyncMock(
        return_value={
            "items": [
                {
                    "id": "provider_refresh_sync:refresh-job-1",
                    "task_type": "provider_refresh_sync",
                    "status": "running",
                    "stage": "refreshing",
                    "title": "刷新并适配全部渠道商",
                    "summary": "正在刷新 3/10 个渠道商",
                    "provider_id": None,
                    "provider_name": None,
                    "created_at": "2026-04-09T02:00:00+00:00",
                    "updated_at": "2026-04-09T02:05:00+00:00",
                    "source_task_id": "refresh-job-1",
                },
                {
                    "id": "provider_import:import-job-1",
                    "task_type": "provider_import",
                    "status": "completed",
                    "stage": "completed",
                    "title": "All-in-Hub 导入",
                    "summary": "新增 Provider 4 个",
                    "provider_id": None,
                    "provider_name": None,
                    "created_at": "2026-04-09T01:00:00+00:00",
                    "updated_at": "2026-04-09T01:10:00+00:00",
                    "source_task_id": "import-job-1",
                },
            ],
            "total": 2,
            "page": 1,
            "page_size": 20,
            "pages": 1,
        }
    )
    monkeypatch.setattr(
        "src.api.admin.async_tasks.routes.list_admin_async_tasks",
        list_mock,
    )

    client = _build_app(object())
    response = client.get("/api/admin/async-tasks")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert [item["task_type"] for item in payload["items"]] == [
        "provider_refresh_sync",
        "provider_import",
    ]
    list_mock.assert_awaited_once()


def test_get_admin_async_task_stats_route_returns_aggregated_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stats_mock = AsyncMock(
        return_value={
            "total": 4,
            "by_status": {
                "pending": 1,
                "submitted": 0,
                "queued": 0,
                "processing": 1,
                "completed": 1,
                "failed": 1,
                "cancelled": 0,
            },
            "by_task_type": {
                "video": 1,
                "provider_import": 1,
                "provider_refresh_sync": 2,
            },
            "today_count": 4,
            "processing_count": 2,
        }
    )
    monkeypatch.setattr(
        "src.api.admin.async_tasks.routes.get_admin_async_task_stats",
        stats_mock,
    )

    client = _build_app(object())
    response = client.get("/api/admin/async-tasks/stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 4
    assert payload["by_task_type"]["provider_refresh_sync"] == 2
    assert payload["processing_count"] == 2
    stats_mock.assert_awaited_once()


def test_get_admin_async_task_detail_route_returns_provider_task_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detail_mock = AsyncMock(
        return_value={
            "id": "provider_refresh_sync:refresh-job-1",
            "task_type": "provider_refresh_sync",
            "status": "completed",
            "stage": "completed",
            "title": "刷新并适配 Provider One",
            "summary": "补建 Endpoint 1 个；同步账号格式 1 个",
            "provider_id": "provider-1",
            "provider_name": "Provider One",
            "created_at": "2026-04-09T02:00:00+00:00",
            "updated_at": "2026-04-09T02:03:00+00:00",
            "source_task_id": "refresh-job-1",
            "detail": {
                "scope": "single",
                "result": {
                    "providers_total": 1,
                    "providers_refreshed": 1,
                    "providers_skipped": 0,
                    "providers_with_errors": 0,
                    "created_endpoint_formats": ["openai:cli"],
                    "updated_key_ids": ["key-1"],
                    "error_preview": [],
                    "failed_providers": [
                        {
                            "provider_name": "Broken Provider",
                            "error": "invalid refresh token",
                        }
                    ],
                    "error": None,
                },
            },
        }
    )
    monkeypatch.setattr(
        "src.api.admin.async_tasks.routes.get_admin_async_task_detail",
        detail_mock,
    )

    client = _build_app(object())
    response = client.get("/api/admin/async-tasks/provider_refresh_sync:refresh-job-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_type"] == "provider_refresh_sync"
    assert payload["detail"]["result"]["created_endpoint_formats"] == ["openai:cli"]
    assert payload["detail"]["result"]["failed_providers"][0]["provider_name"] == "Broken Provider"
    detail_mock.assert_awaited_once()
