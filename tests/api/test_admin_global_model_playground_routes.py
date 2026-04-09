from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
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

    def all(self) -> list[Any]:
        return list(self._rows)


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


@pytest.mark.asyncio
async def test_test_global_model_route_returns_platform_level_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.api.admin import provider_query as provider_query_module
    from src.services.candidate.recorder import CandidateRecorder
    from src.services.scheduling.candidate_builder import CandidateBuilder
    from src.services.task import TaskService

    provider = SimpleNamespace(
        id='provider-1',
        name='Provider One',
        provider_type='custom',
        is_active=True,
        request_timeout=None,
        endpoints=[],
        api_keys=[],
        models=[],
    )
    endpoint = SimpleNamespace(
        id='endpoint-1',
        api_format='openai:chat',
        base_url='https://provider-1.example.com/v1',
        is_active=True,
    )
    api_key = SimpleNamespace(
        id='key-1',
        name='Primary',
        auth_type='api_key',
        api_formats=['openai:chat'],
        is_active=True,
    )
    candidate = SimpleNamespace(
        provider=provider,
        endpoint=endpoint,
        key=api_key,
        is_skipped=False,
        provider_api_format='openai:chat',
        mapping_matched_model=None,
    )

    async def _fake_load_global_model_context(_db: Any, model_name: str) -> Any:
        return SimpleNamespace(id='gm-1', name=model_name, config={}), []

    async def _fake_build_candidates(
        self: Any,
        *,
        db: Any,
        providers: list[Any],
        client_format: str,
        model_name: str,
        model_mappings: list[str] | None,
        affinity_key: str | None,
        is_stream: bool,
    ) -> list[Any]:
        assert db is not None
        assert providers
        assert client_format == 'openai:chat'
        assert model_name == 'gpt-4.1-mini'
        assert model_mappings is None
        assert affinity_key is None
        assert is_stream is False
        return [candidate]

    async def _fake_execute_sync_candidates(self: Any, **_kwargs: Any) -> Any:
        return SimpleNamespace(
            success=True,
            attempt_count=1,
            response={'choices': [{'message': {'content': 'hello from global playground'}}]},
            error_message=None,
            candidate_keys=[],
        )

    def _fake_get_candidate_keys(self: Any, request_id: str) -> list[Any]:
        assert request_id.startswith('provider-test-')
        return [
            SimpleNamespace(
                candidate_index=0,
                retry_index=0,
                key_id='key-1',
                key_name='Primary',
                auth_type='api_key',
                status='success',
                skip_reason=None,
                error_message=None,
                status_code=200,
                latency_ms=120,
                extra_data={
                    'model_test_debug': {
                        'request_url': 'https://provider-1.example.com/v1/chat/completions',
                        'request_body': {'model': 'gpt-4.1-mini'},
                        'response_body': {'choices': [{'message': {'content': 'hello from global playground'}}]},
                    },
                },
            )
        ]

    monkeypatch.setattr(
        provider_query_module,
        '_load_global_model_test_context',
        _fake_load_global_model_context,
    )
    monkeypatch.setattr(CandidateBuilder, '_build_candidates', _fake_build_candidates)
    monkeypatch.setattr(TaskService, 'execute_sync_candidates', _fake_execute_sync_candidates)
    monkeypatch.setattr(CandidateRecorder, 'get_candidate_keys', _fake_get_candidate_keys)

    client = _build_provider_query_app(_FakeDB(providers=[provider]))

    response = client.post(
      '/api/admin/provider-query/test-global-model',
      json={
        'model_name': 'gpt-4.1-mini',
        'api_format': 'openai:chat',
        'request_body': {
          'model': 'gpt-4.1-mini',
          'messages': [{'role': 'user', 'content': 'hello'}],
          'stream': True,
        },
      },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert payload['provider']['id'] == 'provider-1'
    assert payload['provider']['name'] == 'Provider One'
    assert payload['model'] == 'gpt-4.1-mini'
    assert payload['total_candidates'] == 1
    assert payload['attempts'][0]['provider_id'] == 'provider-1'
    assert payload['attempts'][0]['provider_name'] == 'Provider One'
    assert payload['attempts'][0]['endpoint_api_format'] == 'openai:chat'
    assert payload['data']['response']['choices'][0]['message']['content'] == 'hello from global playground'
