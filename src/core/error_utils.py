"""
错误消息处理工具函数
"""

from typing import Optional


def extract_error_message(error: Exception, status_code: Optional[int] = None) -> str:
    """
    从异常中提取错误消息，优先使用上游响应内容

    Args:
        error: 异常对象
        status_code: 可选的 HTTP 状态码，用于构建更详细的错误消息

    Returns:
        错误消息字符串
    """
    # 优先使用 upstream_response 属性（包含上游 Provider 的原始错误）
    upstream_response = getattr(error, "upstream_response", None)
    if upstream_response and isinstance(upstream_response, str) and upstream_response.strip():
        return str(upstream_response)

    # 回退到异常的字符串表示（str 可能为空，如 httpx 超时异常）
    error_str = str(error) or repr(error)
    if status_code is not None:
        return f"HTTP {status_code}: {error_str}"
    return error_str
