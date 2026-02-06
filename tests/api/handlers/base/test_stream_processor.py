import json
from typing import Any

from src.api.handlers.base.response_parser import (
    ParsedChunk,
    ParsedResponse,
    ResponseParser,
    StreamStats,
)
from src.api.handlers.base.stream_context import StreamContext
from src.api.handlers.base.stream_processor import StreamProcessor
from src.utils.sse_parser import SSEEventParser


class DummyParser(ResponseParser):
    def parse_sse_line(self, line: str, stats: StreamStats) -> ParsedChunk | None:
        return None

    def parse_response(self, response: dict[str, Any], status_code: int) -> ParsedResponse:
        return ParsedResponse(raw_response=response, status_code=status_code)

    def extract_usage_from_response(self, response: dict[str, Any]) -> dict[str, int]:
        return {}

    def extract_text_content(self, response: dict[str, Any]) -> str:
        return ""


def test_process_line_strips_newlines_and_finalizes_event() -> None:
    ctx = StreamContext(model="test-model", api_format="openai:chat")
    processor = StreamProcessor(request_id="test-request", default_parser=DummyParser())
    sse_parser = SSEEventParser()

    processor._process_line(ctx, sse_parser, 'data: {"type":"response.completed"}\n')
    processor._process_line(ctx, sse_parser, "\n")

    assert ctx.has_completion is True


def test_process_line_updates_openai_usage_from_usage_only_chunk() -> None:
    ctx = StreamContext(model="test-model", api_format="openai:chat")
    ctx.provider_api_format = "openai:chat"
    processor = StreamProcessor(request_id="test-request", default_parser=DummyParser())
    sse_parser = SSEEventParser()

    usage_chunk = {
        "id": "chatcmpl_test",
        "object": "chat.completion.chunk",
        "choices": [],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }

    processor._process_line(ctx, sse_parser, f"data: {json.dumps(usage_chunk)}\n")
    processor._process_line(ctx, sse_parser, "\n")

    assert ctx.input_tokens == 10
    assert ctx.output_tokens == 5


def test_process_line_handles_openai_usage_chunk_followed_by_done_without_blank_line() -> None:
    ctx = StreamContext(model="test-model", api_format="openai:chat")
    ctx.provider_api_format = "openai:chat"
    processor = StreamProcessor(request_id="test-request", default_parser=DummyParser())
    sse_parser = SSEEventParser()

    usage_chunk = {
        "id": "chatcmpl_test",
        "object": "chat.completion.chunk",
        "choices": [],
        "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
    }

    # Some SSE implementations may emit consecutive data lines without an empty separator.
    processor._process_line(ctx, sse_parser, f"data: {json.dumps(usage_chunk)}\n")
    processor._process_line(ctx, sse_parser, "data: [DONE]\n")
    processor._process_line(ctx, sse_parser, "\n")

    assert ctx.input_tokens == 7
    assert ctx.output_tokens == 3
    assert ctx.has_completion is True
