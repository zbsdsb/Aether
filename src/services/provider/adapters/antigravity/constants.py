"""Antigravity 全局常量定义。

注意：这里的 PROVIDER_TYPE 指的是 Provider.provider_type（用于路由与特判），
不是 endpoint signature（family:kind）。
"""

from __future__ import annotations

import platform
import re
import threading

# ============== API 端点 ==============
PROD_BASE_URL = "https://cloudcode-pa.googleapis.com"
DAILY_BASE_URL = "https://daily-cloudcode-pa.googleapis.com"
SANDBOX_BASE_URL = "https://daily-cloudcode-pa.sandbox.googleapis.com"

# ============== User-Agent ==============
VERSION_FETCH_URL = "https://antigravity-auto-updater-974169037036.us-central1.run.app"
_FALLBACK_VERSION = "1.15.8"
_VERSION_RE = re.compile(r"\d+\.\d+\.\d+")


def _detect_platform_tag() -> str:
    """检测当前运行平台，格式与 Go runtime 保持一致。"""
    os_name = platform.system().lower()  # linux, darwin, windows
    arch = platform.machine().lower()
    if arch in ("x86_64", "amd64"):
        arch = "amd64"
    elif arch in ("aarch64", "arm64"):
        arch = "arm64"
    return f"{os_name}/{arch}"


_PLATFORM_TAG = _detect_platform_tag()

# HTTP Header User-Agent（向后兼容：模块级常量保留，新代码应使用 get_http_user_agent()）
HTTP_USER_AGENT = f"antigravity/{_FALLBACK_VERSION} {_PLATFORM_TAG}"

# V1InternalRequest.userAgent 字段（固定值）
REQUEST_USER_AGENT = "antigravity"

# --- 动态 User-Agent 支持 ---
_ua_lock = threading.Lock()
_ua_version: str = _FALLBACK_VERSION


def get_http_user_agent() -> str:
    """返回当前 HTTP User-Agent 字符串（支持动态版本号更新）。"""
    with _ua_lock:
        return f"antigravity/{_ua_version} {_PLATFORM_TAG}"


def update_user_agent_version(version: str) -> None:
    """更新 User-Agent 中的版本号（由 refresh_user_agent 调用）。"""
    global _ua_version  # noqa: PLW0603
    with _ua_lock:
        _ua_version = version


def parse_version_string(text: str) -> str | None:
    """从任意文本中提取 X.Y.Z 格式的版本号。"""
    m = _VERSION_RE.search(text)
    return m.group(0) if m else None


# ============== URL 可用性 ==============
URL_UNAVAILABLE_TTL_SECONDS = 300  # 5 分钟

# ============== Thinking Signature ==============
DUMMY_THOUGHT_SIGNATURE = "skip_thought_signature_validator"
MIN_SIGNATURE_LENGTH = 50  # 与 Antigravity-Manager 对齐

# ============== Thinking Budget ==============
THINKING_BUDGET_AUTO_CAP = 24576
THINKING_BUDGET_DEFAULT_INJECT = 16000
# 包含这些关键字的模型会自动注入 thinkingConfig（如果缺失）
THINKING_MODELS_AUTO_INJECT_KEYWORDS = ("thinking", "gemini-2.0-pro", "gemini-3-pro")

# ============== Retry ==============
RETRY_429_BASE_SECONDS = 5.0
RETRY_503_BASE_SECONDS = 10.0
RETRY_503_MAX_SECONDS = 60.0
RETRY_500_BASE_SECONDS = 3.0

# ============== v1internal 路径 ==============
V1INTERNAL_PATH_TEMPLATE = "/v1internal:{action}"

# ============== Signature 错误关键字（用于 400 错误检测） ==============
SIGNATURE_ERROR_KEYWORDS = (
    "Invalid `signature`",
    "thinking.signature",
    "thinking.thinking",
    "Corrupted thought signature",
)

# ============== Antigravity System Instruction ==============
ANTIGRAVITY_SYSTEM_INSTRUCTION = (
    "You are Antigravity, a powerful agentic AI coding assistant designed by the "
    "Google Deepmind team working on Advanced Agentic Coding.\n"
    "You are pair programming with a USER to solve their coding task. The task may "
    "require creating a new codebase, modifying or debugging an existing codebase, "
    "or simply answering a question.\n"
    "**Absolute paths only**\n"
    "**Proactiveness**"
)

# ============== JSON Schema 禁止字段 ==============
FORBIDDEN_SCHEMA_FIELDS = frozenset(
    {
        "multipleOf",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "contentEncoding",
        "contentMediaType",
    }
)

__all__ = [
    "ANTIGRAVITY_SYSTEM_INSTRUCTION",
    "DAILY_BASE_URL",
    "DUMMY_THOUGHT_SIGNATURE",
    "FORBIDDEN_SCHEMA_FIELDS",
    "HTTP_USER_AGENT",
    "MIN_SIGNATURE_LENGTH",
    "PROD_BASE_URL",
    "REQUEST_USER_AGENT",
    "RETRY_429_BASE_SECONDS",
    "RETRY_500_BASE_SECONDS",
    "RETRY_503_BASE_SECONDS",
    "RETRY_503_MAX_SECONDS",
    "SANDBOX_BASE_URL",
    "SIGNATURE_ERROR_KEYWORDS",
    "THINKING_BUDGET_AUTO_CAP",
    "THINKING_BUDGET_DEFAULT_INJECT",
    "THINKING_MODELS_AUTO_INJECT_KEYWORDS",
    "URL_UNAVAILABLE_TTL_SECONDS",
    "V1INTERNAL_PATH_TEMPLATE",
    "VERSION_FETCH_URL",
    "get_http_user_agent",
    "parse_version_string",
    "update_user_agent_version",
]
