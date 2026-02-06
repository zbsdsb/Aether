from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.api.handlers.claude.adapter import ClaudeChatAdapter


@dataclass
class _DummyResp:
    status_code: int
    payload: object
    text: str = ""

    def json(self) -> object:  # noqa: D401
        """Return mocked JSON payload."""
        return self.payload


@pytest.mark.asyncio
async def test_claude_fetch_models_paginates_until_has_more_false() -> None:
    page1 = {
        "data": [{"id": "m1"}, {"id": "m2"}],
        "has_more": True,
        "first_id": "m1",
        "last_id": "m2",
    }
    page2 = {
        "data": [{"id": "m3"}],
        "has_more": False,
        "first_id": "m3",
        "last_id": "m3",
    }

    client = SimpleNamespace(
        get=AsyncMock(
            side_effect=[
                _DummyResp(status_code=200, payload=page1),
                _DummyResp(status_code=200, payload=page2),
            ]
        )
    )

    models, err = await ClaudeChatAdapter.fetch_models(
        client,  # type: ignore[arg-type]
        "https://api.anthropic.com",
        "k",
        None,
    )

    assert err is None
    assert [m.get("id") for m in models] == ["m1", "m2", "m3"]
    assert all(m.get("api_format") == "claude:chat" for m in models)

    # Second page should pass after_id=last_id from page1.
    assert client.get.call_count == 2
    _, kwargs2 = client.get.call_args_list[1]
    assert kwargs2.get("params", {}).get("after_id") == "m2"
