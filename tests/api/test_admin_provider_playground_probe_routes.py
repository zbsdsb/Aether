from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.database import get_db


class _FakeQuery:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def options(self, *_args: Any, **_kwargs: Any) -> _FakeQuery:
        return self

    def filter(self, *_args: Any, **_kwargs: Any) -> _FakeQuery:
        return self

    def first(self) -> Any | None:
        return self._rows[0] if self._rows else None


class _FakeDB:
    def __init__(self, providers: list[Any]) -> None:
        self.providers = providers

    def query(self, _model: Any) -> _FakeQuery:
        return _FakeQuery(self.providers)


def _build_provider_query_app(db: _FakeDB) -> TestClient:
    from src.api.admin.provider_query import router
    from src.utils.auth_utils import get_current_user

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id='admin-1', role='admin')
    return TestClient(app)


def test_provider_playground_probe_uses_temporary_protocol_candidate(
    monkeypatch: Any,
) -> None:
    from src.api.admin import provider_query as provider_query_module

    provider = SimpleNamespace(
        id='provider-1',
        name='Provider One',
        provider_type='custom',
        is_active=True,
        endpoints=[
            SimpleNamespace(
                id='endpoint-1',
                api_format='openai:chat',
                base_url='https://provider-1.example.com/v1',
                is_active=True,
            ),
        ],
        api_keys=[
            SimpleNamespace(
                id='key-1',
                name='Primary',
                auth_type='api_key',
                api_formats=['openai:chat'],
                is_active=True,
                internal_priority=1,
            ),
        ],
        models=[],
    )

    async def _fake_run_test_candidates(**kwargs: Any) -> dict[str, Any]:
        candidates = kwargs['candidates']
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.endpoint.api_format == 'openai:cli'
        assert candidate.endpoint.base_url == 'https://provider-1.example.com/v1'
        assert candidate.endpoint.id == 'probe:provider-1:openai:cli'
        assert candidate.key.id == 'key-1'
        assert kwargs['request_mode'] == 'probe'
        assert kwargs['client_format'] == 'openai:cli'
        assert kwargs['default_provider'] == provider
        return {
            'success': True,
            'model': kwargs['model_name'],
            'provider': {'id': provider.id, 'name': provider.name},
            'attempts': [],
            'total_candidates': 1,
            'total_attempts': 1,
            'data': {'probe': True},
            'error': None,
        }

    monkeypatch.setattr(provider_query_module, '_run_test_candidates', _fake_run_test_candidates)

    client = _build_provider_query_app(_FakeDB([provider]))
    response = client.post(
        '/api/admin/provider-query/playground-probe',
        json={
            'provider_id': 'provider-1',
            'model_name': 'gpt-4.1-mini',
            'api_format': 'openai:cli',
            'request_body': {
                'model': 'gpt-4.1-mini',
                'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': 'hello'}]}],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert payload['data']['probe'] is True


def test_provider_playground_probe_returns_400_without_active_endpoint() -> None:
    provider = SimpleNamespace(
        id='provider-1',
        name='Provider One',
        provider_type='custom',
        is_active=True,
        endpoints=[],
        api_keys=[],
        models=[],
    )

    client = _build_provider_query_app(_FakeDB([provider]))
    response = client.post(
        '/api/admin/provider-query/playground-probe',
        json={
            'provider_id': 'provider-1',
            'model_name': 'gpt-4.1-mini',
            'api_format': 'openai:cli',
        },
    )

    assert response.status_code == 400
    assert response.json()['detail'] == 'No active endpoint found to determine probe base URL'
