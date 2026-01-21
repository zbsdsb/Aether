"""
API 格式工具函数

提供格式判断、规范化等工具函数，供整个项目使用。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

if TYPE_CHECKING:
    from src.core.api_format.enums import APIFormat


def is_cli_format(format_id: Union[str, "APIFormat", None]) -> bool:
    """
    判断是否为 CLI 透传格式

    CLI 格式以 _CLI 结尾，不参与格式转换，请求直接透传。

    Args:
        format_id: 格式标识符（字符串或 APIFormat 枚举）

    Returns:
        True 如果是 CLI 格式

    Examples:
        >>> is_cli_format("CLAUDE_CLI")
        True
        >>> is_cli_format("CLAUDE")
        False
        >>> is_cli_format(APIFormat.OPENAI_CLI)
        True
    """
    if format_id is None:
        return False
    if hasattr(format_id, "value"):
        format_id = format_id.value
    return str(format_id).upper().endswith("_CLI")


def get_base_format(format_id: Union[str, "APIFormat", None]) -> Optional[str]:
    """
    获取基础格式（去除 _CLI 后缀）

    Args:
        format_id: 格式标识符

    Returns:
        基础格式字符串，或 None

    Examples:
        >>> get_base_format("CLAUDE_CLI")
        "CLAUDE"
        >>> get_base_format("OPENAI")
        "OPENAI"
    """
    if format_id is None:
        return None
    if hasattr(format_id, "value"):
        format_id = format_id.value
    format_str = str(format_id).upper()
    if format_str.endswith("_CLI"):
        return format_str[:-4]
    return format_str


def normalize_format(format_id: Union[str, "APIFormat", None]) -> Optional[str]:
    """
    规范化格式标识符

    Args:
        format_id: 格式标识符（可能是字符串、枚举或 None）

    Returns:
        大写的格式字符串，或 None
    """
    if format_id is None:
        return None
    if hasattr(format_id, "value"):
        return str(format_id.value).upper()
    return str(format_id).upper()


def is_same_format(
    format1: Union[str, "APIFormat", None],
    format2: Union[str, "APIFormat", None],
) -> bool:
    """
    判断两个格式是否相同

    忽略大小写和枚举/字符串差异。
    """
    return normalize_format(format1) == normalize_format(format2)


def is_convertible_format(format_id: Union[str, "APIFormat", None]) -> bool:
    """
    判断是否为可转换格式（非 CLI）

    可转换格式可以与其他格式进行双向转换。
    CLI 格式为透传模式，不参与转换。
    """
    if format_id is None:
        return False
    return not is_cli_format(format_id)
