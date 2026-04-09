from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.user_me.routes import router as me_router
from src.database import get_db
from src.services.user.model_marketplace import (
    build_marketplace_summary,
    derive_marketplace_tags,
    filter_and_sort_marketplace_items,
    mark_marketplace_badges,
)


def _build_me_app(db: MagicMock, monkeypatch: Any) -> TestClient:
    app = FastAPI()
    app.include_router(me_router)
    app.dependency_overrides[get_db] = lambda: db

    async def _fake_pipeline_run(
        *, adapter: object, http_request: object, db: MagicMock, mode: object
    ) -> object:
        _ = mode
        context = SimpleNamespace(
            db=db,
            user=SimpleNamespace(id="user-1", email="u@example.com", role="user"),
            request=http_request,
            ensure_json_body=lambda: {},
            add_audit_metadata=lambda **_: None,
        )
        return await adapter.handle(context)

    monkeypatch.setattr("src.api.user_me.routes.pipeline.run", _fake_pipeline_run)
    return TestClient(app)


def test_derive_marketplace_tags_supports_name_pattern_and_capability_hints() -> None:
    tags = derive_marketplace_tags(
        name="text-embedding-3-large",
        display_name="Embedding Large",
        supported_capabilities=["context_1m"],
        config={"vision": False, "category": "embedding"},
    )

    assert tags == ["embedding"]


def test_mark_marketplace_badges_marks_recommended_and_most_stable() -> None:
    items = [
        {
            "name": "gpt-4o",
            "provider_count": 4,
            "active_provider_count": 3,
            "success_rate": 0.98,
            "avg_latency_ms": 480,
        },
        {
            "name": "gpt-4.1-mini",
            "provider_count": 2,
            "active_provider_count": 2,
            "success_rate": 0.99,
            "avg_latency_ms": 420,
        },
        {
            "name": "o3",
            "provider_count": 5,
            "active_provider_count": 4,
            "success_rate": 0.82,
            "avg_latency_ms": 1500,
        },
    ]

    marked = mark_marketplace_badges(items)

    by_name = {item["name"]: item for item in marked}
    assert by_name["gpt-4o"]["is_recommended"] is True
    assert by_name["gpt-4o"]["is_most_stable"] is False
    assert by_name["gpt-4.1-mini"]["is_most_stable"] is True
    assert by_name["gpt-4.1-mini"]["is_recommended"] is False
    assert by_name["o3"]["is_recommended"] is False
    assert by_name["o3"]["is_most_stable"] is False


def test_build_marketplace_summary_aggregates_counts_and_success_rate() -> None:
    summary = build_marketplace_summary(
        [
            {
                "provider_count": 4,
                "active_provider_count": 3,
                "success_rate": 0.98,
            },
            {
                "provider_count": 2,
                "active_provider_count": 1,
                "success_rate": 0.5,
            },
            {
                "provider_count": 1,
                "active_provider_count": 0,
                "success_rate": None,
            },
        ]
    )

    assert summary["total_models"] == 3
    assert summary["total_provider_count"] == 7
    assert summary["active_provider_count"] == 4
    assert summary["overall_success_rate"] == 0.82


def test_filter_and_sort_marketplace_items_supports_capability_and_only_available() -> None:
    items = [
        {
            "name": "gpt-4o",
            "brand": "openai",
            "tags": ["coding"],
            "supported_capabilities": ["context_1m"],
            "active_provider_count": 2,
            "provider_count": 3,
            "usage_count": 10,
            "success_rate": 0.95,
            "avg_latency_ms": 450,
        },
        {
            "name": "claude-sonnet-4",
            "brand": "anthropic",
            "tags": ["thinking"],
            "supported_capabilities": ["cache_1h"],
            "active_provider_count": 0,
            "provider_count": 2,
            "usage_count": 8,
            "success_rate": 0.99,
            "avg_latency_ms": 400,
        },
    ]

    filtered = filter_and_sort_marketplace_items(
        items,
        capability="context_1m",
        only_available=True,
        sort_by="success_rate",
        sort_dir="desc",
    )

    assert [item["name"] for item in filtered] == ["gpt-4o"]


def test_user_model_marketplace_route_passes_search_to_service(
    monkeypatch: Any,
) -> None:
    captured: dict[str, object] = {}

    def _fake_build_user_model_marketplace_response(
        *,
        db: object,
        user: object,
        search: str | None = None,
        brand: str | None = None,
        tag: str | None = None,
        capability: str | None = None,
        only_available: bool = False,
        sort_by: str = "provider_count",
        sort_dir: str = "desc",
    ) -> dict[str, object]:
        captured["db"] = db
        captured["user_id"] = getattr(user, "id", None)
        captured["search"] = search
        captured["brand"] = brand
        captured["tag"] = tag
        captured["capability"] = capability
        captured["only_available"] = only_available
        captured["sort_by"] = sort_by
        captured["sort_dir"] = sort_dir
        return {
            "summary": {
                "total_models": 1,
                "total_provider_count": 2,
                "active_provider_count": 1,
                "overall_success_rate": 0.96,
            },
            "models": [
                {
                    "id": "gm-1",
                    "name": "gpt-4o",
                    "display_name": "GPT-4o",
                    "description": "demo",
                    "brand": "openai",
                    "icon_url": None,
                    "is_active": True,
                    "supported_capabilities": ["context_1m"],
                    "tags": ["coding"],
                    "usage_count": 12,
                    "provider_count": 2,
                    "active_provider_count": 1,
                    "endpoint_count": 3,
                    "active_endpoint_count": 2,
                    "supported_api_formats": ["openai:chat"],
                    "success_rate": 0.96,
                    "avg_latency_ms": 520,
                    "is_recommended": True,
                    "is_most_stable": False,
                    "default_price_per_request": None,
                    "default_tiered_pricing": {"tiers": []},
                    "providers": [],
                }
            ],
            "total": 1,
            "generated_at": "2026-04-09T00:00:00Z",
        }

    monkeypatch.setattr(
        "src.api.user_me.routes.build_user_model_marketplace_response",
        _fake_build_user_model_marketplace_response,
    )

    client = _build_me_app(MagicMock(), monkeypatch)

    response = client.get(
        "/api/users/me/model-marketplace",
        params={
            "search": "gpt",
            "brand": "openai",
            "tag": "coding",
            "capability": "context_1m",
            "only_available": "true",
            "sort_by": "success_rate",
            "sort_dir": "asc",
        },
    )

    assert response.status_code == 200
    assert captured["search"] == "gpt"
    assert captured["brand"] == "openai"
    assert captured["tag"] == "coding"
    assert captured["capability"] == "context_1m"
    assert captured["only_available"] is True
    assert captured["sort_by"] == "success_rate"
    assert captured["sort_dir"] == "asc"
    assert captured["user_id"] == "user-1"
    assert response.json()["summary"]["total_models"] == 1
