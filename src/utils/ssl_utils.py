"""
SSL 工具函数
提供统一的 SSL 上下文创建功能
"""

import ssl

from loguru import logger

try:
    import certifi

    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CONTEXT = ssl.create_default_context()

_PROXY_SSL_CONTEXT: ssl.SSLContext | None = None


def get_ssl_context() -> ssl.SSLContext:
    """
    获取 SSL 上下文

    优先使用 certifi 证书包，如果未安装则使用系统默认证书。
    返回模块级缓存的 SSL 上下文实例。

    Returns:
        ssl.SSLContext: SSL 上下文
    """
    return _SSL_CONTEXT


def get_proxy_ssl_context(expected_fingerprint: str | None = None) -> ssl.SSLContext:
    """
    获取用于代理连接的 SSL 上下文（连接 aether-proxy TLS 端口）

    当前使用 CERT_NONE（不验证证书），因为 aether-proxy 使用自签名证书。
    expected_fingerprint 参数预留供未来实现指纹校验。

    Args:
        expected_fingerprint: 预期的证书 SHA-256 指纹（hex，预留参数）

    Returns:
        ssl.SSLContext: 代理专用 SSL 上下文
    """
    global _PROXY_SSL_CONTEXT

    if expected_fingerprint:
        logger.warning("TLS 证书指纹校验尚未实现, fingerprint={} 被忽略", expected_fingerprint)

    if _PROXY_SSL_CONTEXT is None:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        _PROXY_SSL_CONTEXT = ctx
    # TODO: 实现基于 expected_fingerprint 的证书指纹校验
    return _PROXY_SSL_CONTEXT
