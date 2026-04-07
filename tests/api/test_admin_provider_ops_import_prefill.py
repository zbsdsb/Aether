from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.crypto import crypto_service
from src.database import get_db
from src.models.database import Provider, ProviderImportTask


class _FakeQuery:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def filter(self, *_args: Any, **_kwargs: Any) -> _FakeQuery:
        return self

    def order_by(self, *_args: Any, **_kwargs: Any) -> _FakeQuery:
        return self

    def first(self) -> Any | None:
        return self._rows[0] if self._rows else None


@dataclass
class _FakeDB:
    providers: list[Provider] = field(default_factory=list)
    tasks: list[ProviderImportTask] = field(default_factory=list)

    def query(self, model: type[Any]) -> _FakeQuery:
        if model is Provider:
            return _FakeQuery(self.providers)
        if model is ProviderImportTask:
            return _FakeQuery(self.tasks)
        raise AssertionError(f"unexpected model: {model}")


def _build_provider_ops_app(db: _FakeDB) -> TestClient:
    from src.api.admin.provider_ops.routes import router
    from src.utils.auth_utils import require_admin

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_admin] = lambda: object()
    return TestClient(app)


def test_get_imported_auth_prefill_returns_new_api_payload() -> None:
    provider = Provider(
        id="provider-1",
        name="Provider One",
        provider_type="custom",
        website="https://provider-1.example.com",
    )
    task = ProviderImportTask(
        id="task-1",
        provider_id="provider-1",
        endpoint_id=None,
        task_type="pending_reissue",
        status="pending",
        source_kind="all_in_hub",
        source_id="acct-1",
        source_name="Provider One",
        source_origin="https://provider-1.example.com",
        credential_payload=crypto_service.encrypt(
            '{"access_token":"tok-123","session_cookie":"session=abc"}'
        ),
        source_metadata={
            "site_type": "new-api",
            "endpoint_base_url": "https://provider-1.example.com/v1",
            "account_id": "42",
            "has_access_token": True,
            "has_session_cookie": True,
        },
        retry_count=0,
        last_error=None,
        last_attempt_at=None,
        completed_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    client = _build_provider_ops_app(_FakeDB(providers=[provider], tasks=[task]))

    response = client.get("/api/admin/provider-ops/providers/provider-1/imported-auth-prefill")

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["architecture_id"] == "new_api"
    assert payload["base_url"] == "https://provider-1.example.com/v1"
    assert payload["connector"]["auth_type"] == "api_key"
    assert payload["connector"]["config"] == {}
    assert payload["connector"]["credentials"]["cookie"] == "session=abc"
    assert payload["connector"]["credentials"]["api_key"] == "tok-123"
    assert payload["connector"]["credentials"]["user_id"] == "42"
    assert payload["source_summary"]["task_type"] == "pending_reissue"
    assert payload["source_summary"]["site_type"] == "new-api"


def test_get_imported_auth_prefill_returns_available_false_without_import_task() -> None:
    provider = Provider(
        id="provider-1",
        name="Provider One",
        provider_type="custom",
        website="https://provider-1.example.com",
    )
    client = _build_provider_ops_app(_FakeDB(providers=[provider], tasks=[]))

    response = client.get("/api/admin/provider-ops/providers/provider-1/imported-auth-prefill")

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is False
    assert payload["architecture_id"] is None
    assert payload["base_url"] is None
    assert payload["connector"] is None


def test_get_imported_auth_prefill_returns_prefill_only_task_payload() -> None:
    provider = Provider(
        id="provider-1",
        name="Provider One",
        provider_type="custom",
        website="https://provider-1.example.com",
    )
    task = ProviderImportTask(
        id="task-1",
        provider_id="provider-1",
        endpoint_id=None,
        task_type="imported_auth_prefill",
        status="pending",
        source_kind="all_in_hub",
        source_id="acct-1",
        source_name="Provider One",
        source_origin="https://provider-1.example.com",
        credential_payload=crypto_service.encrypt(
            '{"access_token":"tok-123","session_cookie":""}'
        ),
        source_metadata={
            "site_type": "new-api",
            "endpoint_base_url": "https://provider-1.example.com/v1",
            "account_id": "42",
            "has_access_token": True,
            "has_session_cookie": False,
        },
        retry_count=0,
        last_error=None,
        last_attempt_at=None,
        completed_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    client = _build_provider_ops_app(_FakeDB(providers=[provider], tasks=[task]))

    response = client.get("/api/admin/provider-ops/providers/provider-1/imported-auth-prefill")

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["architecture_id"] == "new_api"
    assert payload["base_url"] == "https://provider-1.example.com/v1"
    assert payload["connector"]["credentials"]["api_key"] == "tok-123"
    assert payload["connector"]["credentials"]["user_id"] == "42"
    assert payload["source_summary"]["task_type"] == "imported_auth_prefill"


def test_get_imported_auth_prefill_returns_sub2api_refresh_token_payload() -> None:
    provider = Provider(
        id="provider-1",
        name="Provider One",
        provider_type="custom",
        website="https://sub.example.com",
    )
    task = ProviderImportTask(
        id="task-1",
        provider_id="provider-1",
        endpoint_id=None,
        task_type="imported_auth_prefill",
        status="pending",
        source_kind="all_in_hub",
        source_id="acct-sub2-1",
        source_name="Provider One",
        source_origin="https://sub.example.com",
        credential_payload=crypto_service.encrypt(
            '{"access_token":"tok-123","refresh_token":"rt-123","session_cookie":""}'
        ),
        source_metadata={
            "site_type": "sub2api",
            "endpoint_base_url": "https://sub.example.com",
            "account_id": "42",
            "has_access_token": True,
            "has_refresh_token": True,
            "has_session_cookie": False,
        },
        retry_count=0,
        last_error=None,
        last_attempt_at=None,
        completed_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    client = _build_provider_ops_app(_FakeDB(providers=[provider], tasks=[task]))

    response = client.get("/api/admin/provider-ops/providers/provider-1/imported-auth-prefill")

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["architecture_id"] == "sub2api"
    assert payload["connector"]["auth_type"] == "api_key"
    assert payload["connector"]["credentials"]["refresh_token"] == "rt-123"
    assert payload["source_summary"]["has_refresh_token"] is True


def test_run_pending_proxy_probe_route_returns_summary(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def _fake_probe_pending_provider_proxies(*, db, limit):  # type: ignore[no-untyped-def]
        _ = db
        assert limit == 5
        from src.services.provider_ops.proxy_probe import ProviderProxyProbeSummary

        return ProviderProxyProbeSummary(
            total_selected=1,
            completed=1,
            failed=0,
            skipped=0,
            results=[
                {
                    "provider_id": "provider-1",
                    "provider_name": "Provider One",
                    "status": "completed",
                    "mode": "direct",
                    "message": "direct probe succeeded",
                }
            ],
        )

    monkeypatch.setattr(
        "src.api.admin.provider_ops.routes.probe_pending_provider_proxies",
        _fake_probe_pending_provider_proxies,
    )

    client = _build_provider_ops_app(_FakeDB())
    response = client.post("/api/admin/provider-ops/proxy-probe/run", json={"limit": 5})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_selected"] == 1
    assert payload["completed"] == 1
    assert payload["results"][0]["mode"] == "direct"
