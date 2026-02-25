"""
is_format_compatible 单元测试

覆盖：
- 同格式透传
- CLI 格式允许转换（按 registry 能力）
- 全局开关/端点开关/白黑名单
- 流式转换开关
- 转换器能力校验
"""

from unittest.mock import MagicMock

import pytest

from src.core.api_format.conversion.compatibility import is_format_compatible


def test_same_format_is_compatible() -> None:
    ok, needs_conv, reason = is_format_compatible(
        "claude:chat",
        "claude:chat",
        endpoint_format_acceptance_config=None,
        is_stream=False,
        effective_conversion_enabled=False,
        registry=MagicMock(),
    )
    assert ok is True
    assert needs_conv is False
    assert reason is None


def test_cli_format_convertible_when_converter_supports_full() -> None:
    registry = MagicMock()
    registry.can_convert_full.return_value = True

    ok, needs_conv, reason = is_format_compatible(
        "claude:cli",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": True},
        is_stream=False,
        effective_conversion_enabled=True,
        registry=registry,
    )
    assert ok is True
    assert needs_conv is True
    assert reason is None


def test_global_switch_disabled_falls_back_to_endpoint() -> None:
    """全局开关关闭时回退到端点配置（分层开关设计）"""
    registry = MagicMock()
    registry.can_convert_full.return_value = True

    # 全局 OFF + 端点 enabled -> 允许（端点覆盖全局默认）
    ok, needs_conv, reason = is_format_compatible(
        "claude:chat",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": True},
        is_stream=False,
        effective_conversion_enabled=False,
        registry=registry,
    )
    assert ok is True
    assert needs_conv is True
    assert reason is None


def test_global_switch_disabled_blocks_when_endpoint_not_configured() -> None:
    """全局开关关闭 + 端点未配置 -> 阻止转换"""
    ok, needs_conv, reason = is_format_compatible(
        "claude:chat",
        "openai:chat",
        endpoint_format_acceptance_config=None,
        is_stream=False,
        effective_conversion_enabled=False,
        registry=MagicMock(),
    )
    assert ok is False
    assert needs_conv is False
    assert reason and "未配置" in reason


def test_endpoint_config_none_blocks_conversion() -> None:
    ok, needs_conv, reason = is_format_compatible(
        "claude:chat",
        "openai:chat",
        endpoint_format_acceptance_config=None,
        is_stream=False,
        effective_conversion_enabled=True,
        registry=MagicMock(),
    )
    assert ok is False
    assert needs_conv is False
    assert reason and "未配置" in reason


def test_endpoint_disabled_blocks_conversion() -> None:
    ok, needs_conv, reason = is_format_compatible(
        "claude:chat",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": False},
        is_stream=False,
        effective_conversion_enabled=True,
        registry=MagicMock(),
    )
    assert ok is False
    assert needs_conv is False
    assert reason and "未启用" in reason


def test_accept_formats_allows_only_whitelist() -> None:
    ok, needs_conv, reason = is_format_compatible(
        "claude:chat",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": True, "accept_formats": ["openai:chat"]},
        is_stream=False,
        effective_conversion_enabled=True,
        registry=MagicMock(),
    )
    assert ok is False
    assert needs_conv is False
    assert reason and "不接受" in reason


def test_reject_formats_blocks_blacklist() -> None:
    ok, needs_conv, reason = is_format_compatible(
        "claude:chat",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": True, "reject_formats": ["claude:chat"]},
        is_stream=False,
        effective_conversion_enabled=True,
        registry=MagicMock(),
    )
    assert ok is False
    assert needs_conv is False
    assert reason and "拒绝" in reason


def test_stream_conversion_disabled_blocks_stream() -> None:
    ok, needs_conv, reason = is_format_compatible(
        "claude:chat",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": True, "stream_conversion": False},
        is_stream=True,
        effective_conversion_enabled=True,
        registry=MagicMock(),
    )
    assert ok is False
    assert needs_conv is False
    assert reason and "流式" in reason


def test_converter_support_required() -> None:
    registry = MagicMock()
    registry.can_convert_full.return_value = False

    ok, needs_conv, reason = is_format_compatible(
        "claude:chat",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": True},
        is_stream=False,
        effective_conversion_enabled=True,
        registry=registry,
    )
    assert ok is False
    assert needs_conv is False
    assert reason and "转换器" in reason


def test_conversion_allowed_when_converter_supports_full() -> None:
    registry = MagicMock()
    registry.can_convert_full.return_value = True

    ok, needs_conv, reason = is_format_compatible(
        "claude:chat",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": True, "accept_formats": ["claude:chat"]},
        is_stream=False,
        effective_conversion_enabled=True,
        registry=registry,
    )
    assert ok is True
    assert needs_conv is True
    assert reason is None


# ==================== 同族格式测试 ====================


@pytest.mark.parametrize(
    "client_format, endpoint_format",
    [
        ("claude:cli", "claude:chat"),
        ("claude:chat", "claude:cli"),
        ("gemini:cli", "gemini:chat"),
        ("gemini:chat", "gemini:cli"),
    ],
)
def test_same_data_format_passthrough(client_format: str, endpoint_format: str) -> None:
    """data_format_id 相同的格式对（如 claude:chat / claude:cli）无需开关即可透传"""
    # 即使全局开关 OFF、端点未配置，也应直接透传
    ok, needs_conv, reason = is_format_compatible(
        client_format,
        endpoint_format,
        endpoint_format_acceptance_config=None,
        is_stream=False,
        effective_conversion_enabled=False,
        registry=MagicMock(),
    )
    assert ok is True
    assert needs_conv is False
    assert reason is None


def test_openai_cli_to_openai_needs_conversion() -> None:
    """OPENAI 和 OPENAI_CLI 格式不同（Chat Completions vs Responses API），需要转换"""
    registry = MagicMock()
    registry.can_convert_full.return_value = True

    ok, needs_conv, reason = is_format_compatible(
        "openai:cli",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": True},  # 同族转换也需要端点配置
        is_stream=False,
        effective_conversion_enabled=True,  # 同族转换也需要全局开关
        registry=registry,
    )
    assert ok is True
    assert needs_conv is True  # 需要转换！
    assert reason is None


def test_openai_to_openai_cli_needs_conversion() -> None:
    """OPENAI 和 OPENAI_CLI 格式不同（Chat Completions vs Responses API），需要转换"""
    registry = MagicMock()
    registry.can_convert_full.return_value = True

    ok, needs_conv, reason = is_format_compatible(
        "openai:chat",
        "openai:cli",
        endpoint_format_acceptance_config={"enabled": True},  # 同族转换也需要端点配置
        is_stream=False,
        effective_conversion_enabled=True,  # 同族转换也需要全局开关
        registry=registry,
    )
    assert ok is True
    assert needs_conv is True  # 需要转换！
    assert reason is None


def test_openai_cli_to_openai_stream_needs_conversion() -> None:
    """OPENAI_CLI 流式请求到 OPENAI 也需要转换"""
    registry = MagicMock()
    registry.can_convert_full.return_value = True

    ok, needs_conv, reason = is_format_compatible(
        "openai:cli",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": True},  # 同族转换也需要端点配置
        is_stream=True,
        effective_conversion_enabled=True,  # 同族转换也需要全局开关
        registry=registry,
    )
    assert ok is True
    assert needs_conv is True
    assert reason is None


def test_openai_cli_to_openai_fails_without_converter() -> None:
    """如果转换器不支持，同族转换也会失败"""
    registry = MagicMock()
    registry.can_convert_full.return_value = False

    ok, needs_conv, reason = is_format_compatible(
        "openai:cli",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": True},
        is_stream=False,
        effective_conversion_enabled=True,
        registry=registry,
    )
    assert ok is False
    assert needs_conv is False
    assert reason and "转换器" in reason


def test_openai_cli_to_openai_allowed_when_endpoint_enabled() -> None:
    """同族转换（OPENAI/OPENAI_CLI）全局 OFF 时回退到端点配置"""
    registry = MagicMock()
    registry.can_convert_full.return_value = True

    ok, needs_conv, reason = is_format_compatible(
        "openai:cli",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": True},
        is_stream=False,
        effective_conversion_enabled=False,  # 全局开关关闭
        registry=registry,
    )
    # 全局 OFF + 端点 enabled -> 允许（需要转换）
    assert ok is True
    assert needs_conv is True
    assert reason is None


def test_openai_cli_to_openai_blocked_when_endpoint_disabled() -> None:
    """同族转换（OPENAI/OPENAI_CLI）也受端点开关限制"""
    registry = MagicMock()
    registry.can_convert_full.return_value = True

    ok, needs_conv, reason = is_format_compatible(
        "openai:cli",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": False},  # 端点开关关闭
        is_stream=False,
        effective_conversion_enabled=True,
        registry=registry,
    )
    assert ok is False
    assert needs_conv is False
    assert reason and "未启用" in reason


def test_openai_cli_to_openai_blocked_when_endpoint_not_configured() -> None:
    """同族转换（OPENAI/OPENAI_CLI）也需要端点配置"""
    registry = MagicMock()
    registry.can_convert_full.return_value = True

    ok, needs_conv, reason = is_format_compatible(
        "openai:cli",
        "openai:chat",
        endpoint_format_acceptance_config=None,  # 无端点配置
        is_stream=False,
        effective_conversion_enabled=True,
        registry=registry,
    )
    assert ok is False
    assert needs_conv is False
    assert reason and "未配置" in reason
