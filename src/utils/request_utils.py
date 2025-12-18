"""
请求处理工具函数
提供统一的HTTP请求信息提取功能
"""

from typing import Optional

from fastapi import Request

from src.config import config


def get_client_ip(request: Request) -> str:
    """
    获取客户端真实IP地址

    按优先级检查：
    1. X-Forwarded-For 头（支持代理链，根据可信代理数量提取）
    2. X-Real-IP 头（Nginx 代理）
    3. 直接客户端IP

    安全说明：
    - 此函数根据 TRUSTED_PROXY_COUNT 配置来决定信任的代理层数
    - 当 TRUSTED_PROXY_COUNT=0 时，不信任任何代理头，直接使用连接 IP
    - 当服务直接暴露公网时，应设置 TRUSTED_PROXY_COUNT=0 以防止 IP 伪造

    Args:
        request: FastAPI Request 对象

    Returns:
        str: 客户端IP地址，如果无法获取则返回 "unknown"
    """
    trusted_proxy_count = config.trusted_proxy_count

    # 如果不信任任何代理，直接返回连接 IP
    if trusted_proxy_count == 0:
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    # 优先检查 X-Forwarded-For 头（可能包含代理链）
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For 格式: "client, proxy1, proxy2"
        # 从右往左数 trusted_proxy_count 个，取其左边的第一个
        ips = [ip.strip() for ip in forwarded_for.split(",") if ip.strip()]
        if len(ips) > trusted_proxy_count:
            return ips[-(trusted_proxy_count + 1)]
        elif ips:
            return ips[0]

    # 检查 X-Real-IP 头（通常由 Nginx 设置）
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # 回退到直接客户端IP
    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def get_user_agent(request: Request) -> str:
    """
    获取用户代理字符串

    Args:
        request: FastAPI Request 对象

    Returns:
        str: User-Agent 字符串，如果无法获取则返回 "unknown"
    """
    return request.headers.get("User-Agent", "unknown")


def get_request_id(request: Request) -> Optional[str]:
    """
    获取请求ID（如果存在）

    Args:
        request: FastAPI Request 对象

    Returns:
        Optional[str]: 请求ID，如果不存在则返回 None
    """
    return getattr(request.state, "request_id", None)


def get_request_metadata(request: Request) -> dict:
    """
    获取请求的完整元数据

    Args:
        request: FastAPI Request 对象

    Returns:
        dict: 包含请求元数据的字典
    """
    return {
        "client_ip": get_client_ip(request),
        "user_agent": get_user_agent(request),
        "request_id": get_request_id(request),
        "method": request.method,
        "path": request.url.path,
        "query_params": str(request.query_params) if request.query_params else None,
        "content_type": request.headers.get("Content-Type"),
        "content_length": request.headers.get("Content-Length"),
    }


def extract_ip_from_headers(headers: dict, trusted_proxy_count: Optional[int] = None) -> str:
    """
    从HTTP头字典中提取IP地址（用于中间件等场景）

    Args:
        headers: HTTP头字典
        trusted_proxy_count: 可信代理层数，None 时使用配置值

    Returns:
        str: 客户端IP地址
    """
    if trusted_proxy_count is None:
        trusted_proxy_count = config.trusted_proxy_count

    # 如果不信任任何代理，返回 unknown（调用方需要用其他方式获取连接 IP）
    if trusted_proxy_count == 0:
        return "unknown"

    # 检查 X-Forwarded-For
    forwarded_for = headers.get("x-forwarded-for", "")
    if forwarded_for:
        ips = [ip.strip() for ip in forwarded_for.split(",") if ip.strip()]
        if len(ips) > trusted_proxy_count:
            return ips[-(trusted_proxy_count + 1)]
        elif ips:
            return ips[0]

    # 检查 X-Real-IP
    real_ip = headers.get("x-real-ip", "")
    if real_ip:
        return real_ip.strip()

    return "unknown"
