from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.candidate.schema import CandidateKey
from src.services.candidate.submit import SubmitOutcome
from src.services.task.context import TaskMode
from src.services.task.protocol import AttemptKind
from src.services.task.service import TaskService


@pytest.mark.asyncio
async def test_task_service_execute_async_requires_extract_external_task_id() -> None:
    svc = TaskService(MagicMock())
    with pytest.raises(ValueError):
        await svc.execute(
            task_type="video",
            task_mode=TaskMode.ASYNC,
            api_format="openai:video",
            model_name="m",
            user_api_key=MagicMock(id="u", user_id="user"),
            request_func=AsyncMock(),
            request_id="rid",
        )


@pytest.mark.asyncio
async def test_task_service_execute_async_returns_execution_result() -> None:
    db = MagicMock()
    svc = TaskService(db)

    candidate = SimpleNamespace(
        provider=SimpleNamespace(id="p1", name="prov"),
        endpoint=SimpleNamespace(id="e1"),
        key=SimpleNamespace(id="k1"),
    )
    outcome = SubmitOutcome(
        candidate=candidate,
        candidate_keys=[{"index": 0, "provider_id": "p1"}],
        external_task_id="task_123",
        rule_lookup=None,
        upstream_payload={"id": "x"},
        upstream_headers={"x-test": "1"},
        upstream_status_code=200,
    )

    svc.submit_with_failover = AsyncMock(return_value=outcome)  # type: ignore[method-assign]
    svc._recorder.get_candidate_keys = MagicMock(  # type: ignore[attr-defined]
        return_value=[
            CandidateKey(candidate_index=0, retry_index=0, status="success", provider_id="p1")
        ]
    )

    result = await svc.execute(
        task_type="video",
        task_mode=TaskMode.ASYNC,
        api_format="openai:video",
        model_name="m",
        user_api_key=MagicMock(id="u", user_id="user"),
        request_func=AsyncMock(),
        request_id="rid",
        extract_external_task_id=MagicMock(),
        allow_format_conversion=True,
    )

    assert result.success is True
    assert result.attempt_result is not None
    assert result.attempt_result.kind == AttemptKind.ASYNC_SUBMIT
    assert result.provider_task_id == "task_123"
    assert result.provider_id == "p1"
    assert result.candidate_index == 0
