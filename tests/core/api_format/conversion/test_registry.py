"""
FormatConverterRegistry 单元测试

测试覆盖：
1. 基本注册和查询
2. 能力查询方法
3. 严格模式转换
4. 流式转换签名适配
"""

from typing import Any, Dict, List

import pytest

from src.core.api_format.conversion.exceptions import FormatConversionError
from src.core.api_format.conversion.registry import FormatConverterRegistry
from src.core.api_format.conversion.state import StreamConversionState


# ==================== Mock 转换器 ====================


class MockRequestResponseConverter:
    """只支持请求/响应转换的 Mock 转换器"""

    def convert_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return {"converted": True, "original": request}

    def convert_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        return {"converted": True, "original": response}


class MockNewSignatureStreamConverter:
    """使用新签名 (chunk, state) 的流式转换器"""

    def convert_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return request

    def convert_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        return response

    def convert_stream_chunk(
        self, chunk: Dict[str, Any], state: StreamConversionState
    ) -> List[Dict[str, Any]]:
        """新签名：返回多个事件"""
        events = []
        # 模拟一入多出：第一个 chunk 返回 2 个事件
        if not state.message_started:
            events.append({"type": "message_start", "model": state.model})
            state.message_started = True
        events.append({"type": "content", "data": chunk})
        return events


class MockUnifiedStreamConverter:
    """使用统一签名 (chunk, state) 的流式转换器"""

    def convert_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return request

    def convert_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        return response

    def convert_stream_chunk(
        self,
        chunk: Dict[str, Any],
        state: StreamConversionState,
    ) -> List[Dict[str, Any]]:
        """统一签名：返回事件列表"""
        events = []
        if not state.message_started:
            events.append({"type": "message_start", "model": state.model, "id": state.message_id})
            state.message_started = True
        events.append({"type": "delta", "chunk": chunk})
        return events


class MockReturnsNoneConverter:
    """流式转换返回空列表的转换器"""

    def convert_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return request

    def convert_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        return response

    def convert_stream_chunk(
        self,
        chunk: Dict[str, Any],
        state: StreamConversionState,
    ) -> List[Dict[str, Any]]:
        """对于不支持的事件类型返回空列表"""
        event_type = chunk.get("type")
        if event_type == "message_start":
            return [{"choices": [{"delta": {"role": "assistant"}}], "model": state.model}]
        if event_type == "content_block_delta":
            return [{"choices": [{"delta": {"content": chunk.get("text", "")}}]}]
        return []


class MockFailingConverter:
    """转换时抛出异常的 Mock 转换器"""

    def convert_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        raise ValueError("Request conversion failed")

    def convert_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        raise ValueError("Response conversion failed")

    def convert_stream_chunk(
        self, chunk: Dict[str, Any], state: Any
    ) -> List[Dict[str, Any]]:
        raise ValueError("Stream conversion failed")


# ==================== 测试类 ====================


class TestFormatConverterRegistryBasic:
    """基本注册和查询测试"""

    def test_register_and_get_converter(self) -> None:
        registry = FormatConverterRegistry()
        converter = MockRequestResponseConverter()

        registry.register("OPENAI", "CLAUDE", converter)

        assert registry.get_converter("OPENAI", "CLAUDE") is converter
        assert registry.get_converter("openai", "claude") is converter  # 大小写不敏感

    def test_get_nonexistent_converter_returns_none(self) -> None:
        registry = FormatConverterRegistry()

        assert registry.get_converter("OPENAI", "CLAUDE") is None

    def test_has_converter(self) -> None:
        registry = FormatConverterRegistry()
        converter = MockRequestResponseConverter()

        registry.register("OPENAI", "CLAUDE", converter)

        assert registry.has_converter("OPENAI", "CLAUDE") is True
        assert registry.has_converter("CLAUDE", "OPENAI") is False

    def test_list_converters(self) -> None:
        registry = FormatConverterRegistry()
        registry.register("OPENAI", "CLAUDE", MockRequestResponseConverter())
        registry.register("CLAUDE", "OPENAI", MockRequestResponseConverter())

        converters = registry.list_converters()

        assert ("OPENAI", "CLAUDE") in converters
        assert ("CLAUDE", "OPENAI") in converters
        assert len(converters) == 2


class TestCapabilityQueries:
    """能力查询方法测试"""

    def test_can_convert_request(self) -> None:
        registry = FormatConverterRegistry()
        registry.register("A", "B", MockRequestResponseConverter())

        assert registry.can_convert_request("A", "B") is True
        assert registry.can_convert_request("B", "A") is False

    def test_can_convert_response(self) -> None:
        registry = FormatConverterRegistry()
        registry.register("A", "B", MockRequestResponseConverter())

        assert registry.can_convert_response("A", "B") is True
        assert registry.can_convert_response("B", "A") is False

    def test_can_convert_stream_with_convert_stream_chunk(self) -> None:
        registry = FormatConverterRegistry()
        registry.register("A", "B", MockNewSignatureStreamConverter())

        assert registry.can_convert_stream("A", "B") is True
        assert registry.can_convert_stream("B", "A") is False

    def test_can_convert_stream_unified_signature(self) -> None:
        registry = FormatConverterRegistry()
        registry.register("A", "B", MockUnifiedStreamConverter())

        assert registry.can_convert_stream("A", "B") is True

    def test_can_convert_full_request_response_only(self) -> None:
        """只有请求/响应转换器，不支持流式"""
        registry = FormatConverterRegistry()
        registry.register("OPENAI", "CLAUDE", MockRequestResponseConverter())
        registry.register("CLAUDE", "OPENAI", MockRequestResponseConverter())

        # 不要求流式：通过
        assert registry.can_convert_full("OPENAI", "CLAUDE", require_stream=False) is True
        # 要求流式：失败
        assert registry.can_convert_full("OPENAI", "CLAUDE", require_stream=True) is False

    def test_can_convert_full_with_stream(self) -> None:
        """完整双向转换（含流式）"""
        registry = FormatConverterRegistry()
        registry.register("OPENAI", "CLAUDE", MockNewSignatureStreamConverter())
        registry.register("CLAUDE", "OPENAI", MockNewSignatureStreamConverter())

        assert registry.can_convert_full("OPENAI", "CLAUDE", require_stream=True) is True

    def test_can_convert_full_missing_reverse(self) -> None:
        """缺少反向转换器"""
        registry = FormatConverterRegistry()
        registry.register("OPENAI", "CLAUDE", MockNewSignatureStreamConverter())
        # 没有 CLAUDE -> OPENAI

        assert registry.can_convert_full("OPENAI", "CLAUDE", require_stream=False) is False

    def test_get_supported_targets(self) -> None:
        registry = FormatConverterRegistry()
        registry.register("OPENAI", "CLAUDE", MockRequestResponseConverter())
        registry.register("OPENAI", "GEMINI", MockRequestResponseConverter())
        registry.register("CLAUDE", "OPENAI", MockRequestResponseConverter())

        targets = registry.get_supported_targets("OPENAI")

        assert "CLAUDE" in targets
        assert "GEMINI" in targets
        assert len(targets) == 2


class TestStrictModeConversion:
    """严格模式转换测试"""

    def test_convert_request_strict_success(self) -> None:
        registry = FormatConverterRegistry()
        registry.register("A", "B", MockRequestResponseConverter())

        result = registry.convert_request_strict({"foo": "bar"}, "A", "B")

        assert result["converted"] is True
        assert result["original"] == {"foo": "bar"}

    def test_convert_request_strict_same_format(self) -> None:
        """同格式返回原始请求"""
        registry = FormatConverterRegistry()

        result = registry.convert_request_strict({"foo": "bar"}, "A", "A")

        assert result == {"foo": "bar"}

    def test_convert_request_strict_no_converter(self) -> None:
        registry = FormatConverterRegistry()

        with pytest.raises(FormatConversionError) as exc_info:
            registry.convert_request_strict({"foo": "bar"}, "A", "B")

        assert "未找到转换器" in str(exc_info.value)

    def test_convert_request_strict_converter_fails(self) -> None:
        registry = FormatConverterRegistry()
        registry.register("A", "B", MockFailingConverter())

        with pytest.raises(FormatConversionError) as exc_info:
            registry.convert_request_strict({"foo": "bar"}, "A", "B")

        assert "Request conversion failed" in str(exc_info.value)

    def test_convert_response_strict_success(self) -> None:
        registry = FormatConverterRegistry()
        registry.register("A", "B", MockRequestResponseConverter())

        result = registry.convert_response_strict({"data": "test"}, "A", "B")

        assert result["converted"] is True

    def test_convert_response_strict_no_converter(self) -> None:
        registry = FormatConverterRegistry()

        with pytest.raises(FormatConversionError):
            registry.convert_response_strict({"data": "test"}, "A", "B")


class TestStreamChunkStrictConversion:
    """流式转换严格模式测试"""

    def test_stream_chunk_strict_same_format(self) -> None:
        """同格式返回原始 chunk 包装在列表中"""
        registry = FormatConverterRegistry()
        chunk = {"type": "delta", "text": "hello"}

        result = registry.convert_stream_chunk_strict(chunk, "A", "A")

        assert result == [chunk]

    def test_stream_chunk_strict_no_converter(self) -> None:
        registry = FormatConverterRegistry()

        with pytest.raises(FormatConversionError) as exc_info:
            registry.convert_stream_chunk_strict({"type": "delta"}, "A", "B")

        assert "未找到转换器" in str(exc_info.value)

    def test_stream_chunk_strict_new_signature(self) -> None:
        """测试新签名 (chunk, state) 转换器"""
        registry = FormatConverterRegistry()
        registry.register("A", "B", MockNewSignatureStreamConverter())

        state = StreamConversionState(model="test-model", message_id="msg_123")
        chunk = {"content": "hello"}

        # 第一次调用：应返回 2 个事件（message_start + content）
        result = registry.convert_stream_chunk_strict(chunk, "A", "B", state)

        assert len(result) == 2
        assert result[0]["type"] == "message_start"
        assert result[1]["type"] == "content"
        assert state.message_started is True

        # 第二次调用：应返回 1 个事件（只有 content）
        result2 = registry.convert_stream_chunk_strict({"content": "world"}, "A", "B", state)

        assert len(result2) == 1
        assert result2[0]["type"] == "content"

    def test_stream_chunk_strict_unified_signature(self) -> None:
        """测试统一签名 (chunk, state) 转换器"""
        registry = FormatConverterRegistry()
        registry.register("A", "B", MockUnifiedStreamConverter())

        state = StreamConversionState(
            model="gpt-4", message_id="chatcmpl_123", message_started=False
        )
        chunk = {"text": "hello"}

        result = registry.convert_stream_chunk_strict(chunk, "A", "B", state)

        assert len(result) == 2
        assert result[0]["type"] == "message_start"
        assert result[0]["model"] == "gpt-4"
        assert result[0]["id"] == "chatcmpl_123"
        assert state.message_started is True

    def test_stream_chunk_strict_returns_empty_list(self) -> None:
        """测试转换器返回空列表"""
        registry = FormatConverterRegistry()
        registry.register("CLAUDE", "OPENAI", MockReturnsNoneConverter())

        state = StreamConversionState(model="gpt-4", message_id="msg_123")
        event = {"type": "message_start"}

        result = registry.convert_stream_chunk_strict(event, "CLAUDE", "OPENAI", state)

        assert len(result) == 1
        assert "choices" in result[0]
        assert result[0]["model"] == "gpt-4"

    def test_stream_chunk_strict_unknown_event_returns_empty(self) -> None:
        """不支持的事件类型应返回空列表"""
        registry = FormatConverterRegistry()
        registry.register("CLAUDE", "OPENAI", MockReturnsNoneConverter())

        state = StreamConversionState(model="gpt-4", message_id="msg_123")
        event = {"type": "unknown_event"}  # 不支持的事件类型

        result = registry.convert_stream_chunk_strict(event, "CLAUDE", "OPENAI", state)

        assert result == []

    def test_stream_chunk_strict_converter_fails(self) -> None:
        registry = FormatConverterRegistry()
        registry.register("A", "B", MockFailingConverter())

        state = StreamConversionState(model="test", message_id="123")

        with pytest.raises(FormatConversionError) as exc_info:
            registry.convert_stream_chunk_strict({"data": "test"}, "A", "B", state)

        assert "流式块转换失败" in str(exc_info.value)


class TestNonStrictConversion:
    """非严格模式转换测试（失败时返回原始数据）"""

    def test_convert_request_fallback_on_failure(self) -> None:
        registry = FormatConverterRegistry()
        registry.register("A", "B", MockFailingConverter())

        original = {"foo": "bar"}
        result = registry.convert_request(original, "A", "B")

        # 非严格模式：失败时返回原始请求
        assert result == original

    def test_convert_response_fallback_on_failure(self) -> None:
        registry = FormatConverterRegistry()
        registry.register("A", "B", MockFailingConverter())

        original = {"data": "test"}
        result = registry.convert_response(original, "A", "B")

        assert result == original

    def test_convert_stream_chunk_fallback_on_failure(self) -> None:
        registry = FormatConverterRegistry()
        registry.register("A", "B", MockFailingConverter())

        original = {"chunk": "data"}
        result = registry.convert_stream_chunk(original, "A", "B")

        assert result == [original]
