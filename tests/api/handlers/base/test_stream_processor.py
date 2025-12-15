from typing import Any, Dict, Optional

from src.api.handlers.base.response_parser import ParsedChunk, ParsedResponse, ResponseParser, StreamStats
from src.api.handlers.base.stream_context import StreamContext
from src.api.handlers.base.stream_processor import StreamProcessor
from src.utils.sse_parser import SSEEventParser


class DummyParser(ResponseParser):
    def parse_sse_line(self, line: str, stats: StreamStats) -> Optional[ParsedChunk]:
        return None

    def parse_response(self, response: Dict[str, Any], status_code: int) -> ParsedResponse:
        return ParsedResponse(raw_response=response, status_code=status_code)

    def extract_usage_from_response(self, response: Dict[str, Any]) -> Dict[str, int]:
        return {}

    def extract_text_content(self, response: Dict[str, Any]) -> str:
        return ""


def test_process_line_strips_newlines_and_finalizes_event() -> None:
    ctx = StreamContext(model="test-model", api_format="OPENAI")
    processor = StreamProcessor(request_id="test-request", default_parser=DummyParser())
    sse_parser = SSEEventParser()

    processor._process_line(ctx, sse_parser, 'data: {"type":"response.completed"}\n')
    processor._process_line(ctx, sse_parser, "\n")

    assert ctx.has_completion is True

