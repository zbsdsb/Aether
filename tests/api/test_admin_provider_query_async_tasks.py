from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.admin.provider_query import router as provider_query_router
from src.database.database import get_db
from src.utils.auth_utils import get_current_user


def _build_app(db: object) -> TestClient:
    app = FastAPI()
    app.include_router(provider_query_router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="admin-1",
        username="admin",
        role="admin",
    )
    return TestClient(app)


def test_submit_provider_refresh_sync_job_route_returns_task_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submit_mock = AsyncMock(return_value="refresh-job-1")
    monkeypatch.setattr(
        "src.api.admin.provider_query.submit_provider_refresh_sync_job",
        submit_mock,
    )

    client = _build_app(object())
    response = client.post(
        "/api/admin/provider-query/models/refresh-sync/submit",
        json={"provider_id": "provider-1", "api_key_id": "key-1"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "task_id": "refresh-job-1",
        "status": "pending",
        "stage": "queued",
        "message": "刷新并适配任务已提交，后台处理中",
    }
    submit_mock.assert_awaited_once()


def test_submit_provider_refresh_sync_all_job_route_returns_task_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submit_mock = AsyncMock(return_value="refresh-all-job-1")
    monkeypatch.setattr(
        "src.api.admin.provider_query.submit_provider_refresh_sync_all_job",
        submit_mock,
    )

    client = _build_app(object())
    response = client.post(
        "/api/admin/provider-query/models/refresh-sync-all/submit",
        json={"only_active": True},
    )

    assert response.status_code == 200
    assert response.json()["task_id"] == "refresh-all-job-1"
    assert response.json()["status"] == "pending"
    assert response.json()["stage"] == "queued"
    submit_mock.assert_awaited_once()


def test_get_provider_refresh_sync_job_route_returns_status_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_mock = AsyncMock(
        return_value={
            "task_id": "refresh-job-1",
            "status": "running",
            "stage": "refreshing",
            "message": "正在刷新 3/10 个渠道商",
            "scope": "all",
            "provider_id": None,
            "provider_name": None,
            "created_at": "2026-04-09T01:00:00+00:00",
            "updated_at": "2026-04-09T01:05:00+00:00",
            "result": None,
        }
    )
    monkeypatch.setattr(
        "src.api.admin.provider_query.get_provider_refresh_sync_job",
        get_mock,
    )

    client = _build_app(object())
    response = client.get("/api/admin/provider-query/models/refresh-sync/tasks/refresh-job-1")

    assert response.status_code == 200
    assert response.json()["task_id"] == "refresh-job-1"
    assert response.json()["stage"] == "refreshing"
    get_mock.assert_awaited_once_with("refresh-job-1")


def test_list_provider_refresh_sync_jobs_route_returns_recent_jobs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    list_mock = AsyncMock(
        return_value={
            "items": [
                {
                    "task_id": "refresh-job-2",
                    "status": "completed",
                    "stage": "completed",
                    "message": "已完成",
                    "scope": "single",
                    "provider_id": "provider-2",
                    "provider_name": "Provider Two",
                    "created_at": "2026-04-09T02:00:00+00:00",
                    "updated_at": "2026-04-09T02:01:00+00:00",
                    "result": {
                        "providers_total": 1,
                        "providers_refreshed": 1,
                        "providers_skipped": 0,
                        "providers_with_errors": 0,
                        "created_endpoint_formats": ["openai:cli"],
                        "updated_key_ids": ["key-2"],
                        "error_preview": [],
                        "failed_providers": [],
                        "error": None,
                    },
                }
            ],
            "total": 1,
        }
    )
    monkeypatch.setattr(
        "src.api.admin.provider_query.list_provider_refresh_sync_jobs",
        list_mock,
    )

    client = _build_app(object())
    response = client.get("/api/admin/provider-query/models/refresh-sync/tasks", params={"limit": 5})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["task_id"] == "refresh-job-2"
    assert payload["items"][0]["result"]["created_endpoint_formats"] == ["openai:cli"]
    assert payload["items"][0]["result"]["failed_providers"] == []
    list_mock.assert_awaited_once_with(limit=5)
