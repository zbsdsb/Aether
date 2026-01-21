"""
转换器协议定义

定义转换器必须实现的方法签名，用于类型检查和文档说明。
"""

from __future__ import annotations

from typing import Any, Dict, List, Protocol, runtime_checkable


@runtime_checkable
class RequestConverter(Protocol):
    """请求转换器协议"""

    def convert_request(self, request: Dict[str, Any]) -> Dict[str, Any]: ...


@runtime_checkable
class ResponseConverter(Protocol):
    """响应转换器协议"""

    def convert_response(self, response: Dict[str, Any]) -> Dict[str, Any]: ...


@runtime_checkable
class StreamChunkConverter(Protocol):
    """
    流式响应块转换器协议

    统一签名：(chunk, state) -> List[Dict]

    说明：
    - chunk: 单个流式事件/块
    - state: 跨 chunk 的转换状态（StreamConversionState 或 GeminiStreamConversionState）
    - 返回: 转换后的事件列表（可能 0-N 个）

    注意：
    - 所有流式转换器必须实现此签名
    - state 参数用于跨 chunk 维护状态（如累积文本、消息 ID 等）
    """

    def convert_stream_chunk(
        self,
        chunk: Dict[str, Any],
        state: Any,
    ) -> List[Dict[str, Any]]: ...


__all__ = [
    "RequestConverter",
    "ResponseConverter",
    "StreamChunkConverter",
]
