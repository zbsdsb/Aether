from __future__ import annotations

from types import SimpleNamespace
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.candidate.failover import FailoverEngine
from src.services.candidate.policy import RetryMode, RetryPolicy, SkipPolicy
from src.services.orchestration.error_classifier import ErrorAction
from src.services.task.protocol import AttemptKind, AttemptResult


def _make_candidate(
    *,
    provider_id: str = "p1",
    provider_name: str = "prov",
    endpoint_id: str = "e1",
    key_id: str = "k1",
    key_name: str = "key",
    auth_type: str = "api_key",
    priority: int = 0,
    is_cached: bool = False,
    is_skipped: bool = False,
    skip_reason: str | None = None,
    needs_conversion: bool = False,
    provider_max_retries: int | None = None,
) -> SimpleNamespace:
    provider = SimpleNamespace(id=provider_id, name=provider_name, max_retries=provider_max_retries)
    endpoint = SimpleNamespace(id=endpoint_id)
    key = SimpleNamespace(id=key_id, name=key_name, auth_type=auth_type, priority=priority)
    return SimpleNamespace(
        provider=provider,
        endpoint=endpoint,
        key=key,
        is_cached=is_cached,
        is_skipped=is_skipped,
        skip_reason=skip_reason,
        needs_conversion=needs_conversion,
    )


class _StubErrorClassifier:
    def __init__(self, *, action: ErrorAction, client_error: bool = False) -> None:
        self._action = action
        self._client_error = client_error

    def is_client_error(self, _text: str | None) -> bool:
        return self._client_error

    def classify(
        self, _error: Exception, *, has_retry_left: bool = False
    ) -> ErrorAction:  # noqa: ARG002
        return self._action


@pytest.mark.asyncio
async def test_failover_engine_success_first_candidate() -> None:
    db = MagicMock()
    engine = FailoverEngine(db, error_classifier=_StubErrorClassifier(action=ErrorAction.BREAK))

    candidates = [_make_candidate(provider_id="p1"), _make_candidate(provider_id="p2")]

    attempt = AsyncMock(
        return_value=AttemptResult(
            kind=AttemptKind.SYNC_RESPONSE,
            http_status=200,
            http_headers={},
            response_body={"ok": True},
        )
    )

    result = await engine.execute(
        candidates=candidates,
        attempt_func=attempt,
        retry_policy=RetryPolicy(mode=RetryMode.DISABLED, max_retries=1),
        skip_policy=SkipPolicy(),
        request_id=None,
    )

    assert result.success is True
    assert result.candidate_index == 0
    assert result.attempt_count == 1
    assert result.provider_id == "p1"
    assert result.response == {"ok": True}
    assert attempt.await_count == 1


@pytest.mark.asyncio
async def test_failover_engine_continue_to_next_candidate_on_error() -> None:
    db = MagicMock()
    engine = FailoverEngine(db, error_classifier=_StubErrorClassifier(action=ErrorAction.BREAK))

    candidates = [_make_candidate(provider_id="p1"), _make_candidate(provider_id="p2")]

    attempt = AsyncMock(
        side_effect=[
            RuntimeError("boom"),
            AttemptResult(
                kind=AttemptKind.SYNC_RESPONSE,
                http_status=200,
                http_headers={},
                response_body={"ok": True},
            ),
        ]
    )

    result = await engine.execute(
        candidates=candidates,
        attempt_func=attempt,
        retry_policy=RetryPolicy(mode=RetryMode.DISABLED, max_retries=1),
        skip_policy=SkipPolicy(),
        request_id=None,
    )

    assert result.success is True
    assert result.candidate_index == 1
    assert result.provider_id == "p2"
    assert result.attempt_count == 2
    assert attempt.await_count == 2


@pytest.mark.asyncio
async def test_failover_engine_retry_same_candidate_when_classifier_says_continue() -> None:
    db = MagicMock()
    # ErrorAction.CONTINUE => retry current candidate (mapped to FailoverAction.RETRY)
    engine = FailoverEngine(db, error_classifier=_StubErrorClassifier(action=ErrorAction.CONTINUE))

    candidates = [_make_candidate(provider_id="p1", is_cached=True, provider_max_retries=2)]

    attempt = AsyncMock(
        side_effect=[
            RuntimeError("transient"),
            AttemptResult(
                kind=AttemptKind.SYNC_RESPONSE,
                http_status=200,
                http_headers={},
                response_body={"ok": True},
            ),
        ]
    )

    result = await engine.execute(
        candidates=candidates,
        attempt_func=attempt,
        retry_policy=RetryPolicy(mode=RetryMode.ON_DEMAND, max_retries=2),
        skip_policy=SkipPolicy(),
        request_id=None,
    )

    assert result.success is True
    assert result.candidate_index == 0
    assert result.attempt_count == 2
    assert attempt.await_count == 2


@pytest.mark.asyncio
async def test_failover_engine_stop_when_classifier_raises() -> None:
    db = MagicMock()
    engine = FailoverEngine(db, error_classifier=_StubErrorClassifier(action=ErrorAction.RAISE))

    candidates = [_make_candidate(provider_id="p1"), _make_candidate(provider_id="p2")]
    attempt = AsyncMock(side_effect=RuntimeError("client-ish"))

    result = await engine.execute(
        candidates=candidates,
        attempt_func=attempt,
        retry_policy=RetryPolicy(mode=RetryMode.DISABLED, max_retries=1),
        skip_policy=SkipPolicy(),
        request_id=None,
    )

    assert result.success is False
    assert result.error_type == "RuntimeError"
    assert result.attempt_count == 1
    # should not try candidate 2
    assert attempt.await_count == 1


async def _stream_two_chunks() -> AsyncIterator[bytes]:
    yield b"chunk1"
    yield b"chunk2"


async def _empty_stream() -> AsyncIterator[bytes]:
    if False:  # pragma: no cover
        yield b""
    return


@pytest.mark.asyncio
async def test_failover_engine_stream_probe_wraps_first_chunk() -> None:
    db = MagicMock()
    engine = FailoverEngine(db, error_classifier=_StubErrorClassifier(action=ErrorAction.BREAK))

    candidates = [_make_candidate(provider_id="p1")]
    attempt = AsyncMock(
        return_value=AttemptResult(
            kind=AttemptKind.STREAM,
            http_status=200,
            http_headers={},
            stream_iterator=_stream_two_chunks(),
        )
    )

    result = await engine.execute(
        candidates=candidates,
        attempt_func=attempt,
        retry_policy=RetryPolicy(mode=RetryMode.DISABLED, max_retries=1),
        skip_policy=SkipPolicy(),
        request_id=None,
    )

    assert result.success is True
    assert result.attempt_result is not None
    assert result.attempt_result.kind == AttemptKind.STREAM

    collected: list[bytes] = []
    assert result.response is not None
    async for chunk in result.response:  # type: ignore[union-attr]
        collected.append(chunk)
    assert collected == [b"chunk1", b"chunk2"]


@pytest.mark.asyncio
async def test_failover_engine_stream_probe_empty_triggers_failover() -> None:
    db = MagicMock()
    engine = FailoverEngine(db, error_classifier=_StubErrorClassifier(action=ErrorAction.BREAK))

    candidates = [_make_candidate(provider_id="p1"), _make_candidate(provider_id="p2")]

    attempt = AsyncMock(
        side_effect=[
            AttemptResult(
                kind=AttemptKind.STREAM,
                http_status=200,
                http_headers={},
                stream_iterator=_empty_stream(),
            ),
            AttemptResult(
                kind=AttemptKind.SYNC_RESPONSE,
                http_status=200,
                http_headers={},
                response_body={"ok": True},
            ),
        ]
    )

    result = await engine.execute(
        candidates=candidates,
        attempt_func=attempt,
        retry_policy=RetryPolicy(mode=RetryMode.DISABLED, max_retries=1),
        skip_policy=SkipPolicy(),
        request_id=None,
    )

    assert result.success is True
    assert result.candidate_index == 1
    assert result.attempt_count == 2


@pytest.mark.asyncio
async def test_failover_engine_pre_expand_marks_unused_slots_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = MagicMock()
    engine = FailoverEngine(db, error_classifier=_StubErrorClassifier(action=ErrorAction.BREAK))

    # patch low-level record updater to observe unused marking
    engine._update_record = MagicMock()  # type: ignore[method-assign]
    engine.db.commit = MagicMock()  # type: ignore[method-assign]
    engine._commit_before_await = MagicMock()  # type: ignore[method-assign]

    c0 = _make_candidate(provider_id="p1", is_cached=True, provider_max_retries=2)
    c1 = _make_candidate(provider_id="p2", is_cached=False)

    attempt = AsyncMock(
        return_value=AttemptResult(
            kind=AttemptKind.SYNC_RESPONSE,
            http_status=200,
            http_headers={},
            response_body={"ok": True},
        )
    )

    record_map = {
        (0, 0): "r00",
        (0, 1): "r01",
        (1, 0): "r10",
    }

    result = await engine.execute(
        candidates=[c0, c1],
        attempt_func=attempt,
        retry_policy=RetryPolicy(mode=RetryMode.PRE_EXPAND, max_retries=2),
        skip_policy=SkipPolicy(),
        request_id=None,
        candidate_record_map=record_map,
    )

    assert result.success is True

    # Ensure we marked the remaining slots unused (r01 + r10)
    unused_record_ids = {
        call.args[0]
        for call in engine._update_record.call_args_list  # type: ignore[attr-defined]
        if call.kwargs.get("status") == "unused"
    }
    assert unused_record_ids == {"r01", "r10"}
