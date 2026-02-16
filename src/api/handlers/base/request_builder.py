"""
请求构建器 - 透传模式

透传模式 (Passthrough): CLI 和 Chat 等场景，原样转发请求体和头部
- 清理敏感头部：authorization, x-api-key, host, content-length 等
- 保留所有其他头部和请求体字段
- 适用于：Claude CLI、OpenAI CLI、Chat API 等场景

使用方式：
    builder = PassthroughRequestBuilder()
    payload, headers = builder.build(original_body, original_headers, endpoint, key)
"""

from __future__ import annotations

import copy
import re
from abc import ABC, abstractmethod
from typing import Any

from src.core.api_format import (
    UPSTREAM_DROP_HEADERS,
    HeaderBuilder,
    get_auth_config_for_endpoint,
    make_signature_key,
)
from src.core.crypto import crypto_service
from src.core.provider_auth_types import ProviderAuthInfo
from src.models.endpoint_models import _CONDITION_OPS, _TYPE_IS_VALUES, parse_re_flags
from src.services.provider.auth import get_provider_auth

# ==============================================================================
# 统一的头部配置常量
# ==============================================================================

# 兼容别名：历史代码使用 SENSITIVE_HEADERS 命名
SENSITIVE_HEADERS: frozenset[str] = UPSTREAM_DROP_HEADERS

# 请求体中受保护的字段（不能被 body_rules 修改）
PROTECTED_BODY_FIELDS: frozenset[str] = frozenset(
    {
        "model",  # 模型名由系统管理
        "stream",  # 流式标志由系统管理
    }
)


# ==============================================================================
# 测试请求常量与辅助函数
# ==============================================================================

# 标准测试请求体（OpenAI 格式）
# 用于 check_endpoint 等测试场景，使用简单安全的消息内容避免触发安全过滤
DEFAULT_TEST_REQUEST: dict[str, Any] = {
    "messages": [{"role": "user", "content": "Hi"}],
    "max_tokens": 5,
    "temperature": 0,
}


def get_test_request_data(request_data: dict[str, Any] | None = None) -> dict[str, Any]:
    """获取测试请求数据

    如果传入 request_data，则合并到默认测试请求中；
    否则使用默认测试请求。

    Args:
        request_data: 用户提供的请求数据（会覆盖默认值）

    Returns:
        合并后的测试请求数据（OpenAI 格式）
    """
    if request_data:
        merged = DEFAULT_TEST_REQUEST.copy()
        merged.update(request_data)
        return merged
    return DEFAULT_TEST_REQUEST.copy()


def build_test_request_body(
    format_id: str,
    request_data: dict[str, Any] | None = None,
    *,
    target_variant: str | None = None,
) -> dict[str, Any]:
    """构建测试请求体，自动处理格式转换

    使用格式转换注册表将 OpenAI 格式的测试请求转换为目标格式。

    Args:
        format_id: 目标 endpoint signature（如 "claude:chat", "gemini:chat", "openai:cli"）
        request_data: 可选的请求数据，会与默认测试请求合并
        target_variant: 目标变体（如 "codex"），用于同格式但有细微差异的上游

    Returns:
        转换为目标 API 格式的请求体
    """
    from src.core.api_format.conversion import (
        format_conversion_registry,
        register_default_normalizers,
    )

    register_default_normalizers()

    # 获取测试请求数据（OpenAI 格式）
    source_data = get_test_request_data(request_data)

    # 直接使用目标格式进行转换，不再转换为基础格式
    # 这样 openai:cli 会正确转换为 Responses API 格式
    return format_conversion_registry.convert_request(
        source_data,
        make_signature_key("openai", "chat"),
        format_id,
        target_variant=target_variant,
    )


# ==============================================================================
# 请求体规则应用
# ==============================================================================


# 路径段类型：str 表示 dict key，int 表示数组索引
PathSegment = str | int


def _parse_path(path: str) -> list[PathSegment]:
    """
    解析路径，支持点号分隔、转义和数组索引。

    Examples:
        "metadata.user.name"       -> ["metadata", "user", "name"]
        "config\\.v1.enabled"      -> ["config.v1", "enabled"]
        "messages[0].content"      -> ["messages", 0, "content"]
        "data[0].items[2].name"    -> ["data", 0, "items", 2, "name"]
        "messages[-1]"             -> ["messages", -1]
        "matrix[0][1]"             -> ["matrix", 0, 1]

    约束：
        - 不允许空段（例如：".a" / "a." / "a..b"），遇到则返回空列表表示无效路径。
        - 仅对 "\\." 做特殊处理；其他反斜杠组合按字面量保留。
        - 数组索引必须是整数（支持负数索引）。
    """
    raw = (path or "").strip()
    if not raw:
        return []

    parts: list[PathSegment] = []
    current: list[str] = []
    expect_key = True  # 是否期望下一个片段是 dict key

    i = 0
    while i < len(raw):
        ch = raw[i]

        # 转义点号：\\.
        if ch == "\\" and i + 1 < len(raw) and raw[i + 1] == ".":
            current.append(".")
            expect_key = False
            i += 2
            continue

        # 点号分隔符
        if ch == ".":
            if current:
                parts.append("".join(current))
                current = []
            elif expect_key:
                # 空段（如 ".a" 或 "a..b"）
                return []
            expect_key = True
            i += 1
            continue

        # 数组索引：[N]
        if ch == "[":
            # 先将当前累积的 key 入栈
            if current:
                parts.append("".join(current))
                current = []

            # 查找闭合括号
            j = i + 1
            while j < len(raw) and raw[j] != "]":
                j += 1
            if j >= len(raw):
                return []  # 未闭合的括号

            index_str = raw[i + 1 : j].strip()
            if not index_str:
                return []  # 空索引

            try:
                idx = int(index_str)
            except ValueError:
                return []  # 非整数索引

            parts.append(idx)
            expect_key = False
            i = j + 1
            continue

        current.append(ch)
        expect_key = False
        i += 1

    # 收尾：将剩余的 key 入栈
    if current:
        parts.append("".join(current))
    elif expect_key:
        # 尾部悬挂的点号（如 "a."）
        return []

    return parts if parts else []


def _get_nested_value(obj: Any, path: str) -> tuple[bool, Any]:
    """
    获取嵌套值，支持 dict 和 list 混合遍历

    Returns:
        (found, value) - found 为 True 时 value 有效
    """
    parts = _parse_path(path)
    if not parts:
        return False, None

    current: Any = obj
    for segment in parts:
        if isinstance(segment, int):
            if isinstance(current, list):
                try:
                    current = current[segment]
                except IndexError:
                    return False, None
            else:
                return False, None
        else:
            if isinstance(current, dict) and segment in current:
                current = current[segment]
            else:
                return False, None
    return True, current


def _set_nested_value(obj: dict[str, Any], path: str, value: Any) -> bool:
    """
    设置嵌套值，支持 dict 和 list 混合遍历。

    - dict 中间层：下一段为 str key 时自动创建（覆写语义）；下一段为 int 时要求已存在 list。
    - list 中间层：必须已存在且索引有效。
    - list 元素赋值：要求索引在范围内。

    Returns:
        True: 写入成功
        False: 路径无效或结构不匹配
    """
    parts = _parse_path(path)
    if not parts:
        return False

    current: Any = obj
    for i in range(len(parts) - 1):
        segment = parts[i]
        next_segment = parts[i + 1]

        if isinstance(segment, int):
            # 遍历数组元素
            if not isinstance(current, list):
                return False
            try:
                current = current[segment]
            except IndexError:
                return False
        else:
            # 遍历 dict key
            if not isinstance(current, dict):
                return False
            child = current.get(segment)

            if isinstance(next_segment, int):
                # 下一段是数组索引 → child 必须已经是 list
                if not isinstance(child, list):
                    return False
                current = child
            else:
                # 下一段是 dict key → 自动创建 dict（覆写语义）
                if not isinstance(child, dict):
                    child = {}
                    current[segment] = child
                current = child

    # 写入最终值
    last = parts[-1]
    if isinstance(last, int):
        if not isinstance(current, list):
            return False
        try:
            current[last] = value
            return True
        except IndexError:
            return False
    else:
        if not isinstance(current, dict):
            return False
        current[last] = value
        return True


def _delete_nested_value(obj: dict[str, Any], path: str) -> bool:
    """
    删除嵌套值，支持 dict 和 list 混合遍历

    对于 list 元素，使用 del 删除（会移动后续元素的索引）。

    Returns:
        True: 删除成功
        False: 路径不存在或无效
    """
    parts = _parse_path(path)
    if not parts:
        return False

    current: Any = obj
    for segment in parts[:-1]:
        if isinstance(segment, int):
            if isinstance(current, list):
                try:
                    current = current[segment]
                except IndexError:
                    return False
            else:
                return False
        else:
            if isinstance(current, dict) and segment in current:
                current = current[segment]
            else:
                return False

    last = parts[-1]
    if isinstance(last, int):
        if isinstance(current, list):
            try:
                del current[last]
                return True
            except IndexError:
                return False
        return False
    else:
        if isinstance(current, dict) and last in current:
            del current[last]
            return True
        return False


def _rename_nested_value(obj: dict[str, Any], from_path: str, to_path: str) -> bool:
    """
    重命名嵌套值（移动到新路径），支持 dict 和 list 混合遍历

    Returns:
        True: 重命名成功
        False: 源路径不存在或路径无效
    """
    src = (from_path or "").strip()
    dst = (to_path or "").strip()
    if not src or not dst:
        return False
    if src == dst:
        found, _ = _get_nested_value(obj, src)
        return found

    found, value = _get_nested_value(obj, src)
    if not found:
        return False

    # 先 set 再 delete，避免 set 失败时源值已被删除导致数据丢失
    if not _set_nested_value(obj, dst, value):
        return False
    _delete_nested_value(obj, src)
    return True


def _is_protected_path(parts: list[PathSegment], protected_lower: frozenset[str]) -> bool:
    """检查路径的顶层 key 是否为受保护字段（int 索引不可能是受保护字段）"""
    if not parts:
        return False
    first = parts[0]
    return isinstance(first, str) and first.lower() in protected_lower


def _extract_path(
    rule: dict[str, Any],
    protected_lower: frozenset[str],
    key: str = "path",
) -> str | None:
    """从规则中提取并校验 path 字段，返回 strip 后的路径或 None（无效/受保护时）。"""
    raw = rule.get(key, "")
    if not isinstance(raw, str):
        return None
    path = raw.strip()
    parts = _parse_path(path)
    if not parts:
        return None
    if _is_protected_path(parts, protected_lower):
        return None
    return path


_ORIGINAL_PLACEHOLDER = "{{$original}}"


def _contains_original_placeholder(value: Any) -> bool:
    """递归检查 value 中是否包含 {{$original}} 占位符"""
    if isinstance(value, str):
        return _ORIGINAL_PLACEHOLDER in value
    if isinstance(value, dict):
        return any(_contains_original_placeholder(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_original_placeholder(item) for item in value)
    return False


def _resolve_original_placeholder(template: Any, original: Any) -> Any:
    """递归解析模板中的 {{$original}} 占位符。

    - 字符串完全匹配 {{$original}} → 直接返回原值（保留原始类型）
    - 字符串部分包含 {{$original}} → str(original) 插值
    - dict → 递归处理每个 value
    - list → 递归处理每个元素
    - 其他 → 原样返回
    """
    if isinstance(template, str):
        if template == _ORIGINAL_PLACEHOLDER:
            return original
        if _ORIGINAL_PLACEHOLDER in template:
            return template.replace(_ORIGINAL_PLACEHOLDER, str(original))
        return template
    if isinstance(template, dict):
        return {k: _resolve_original_placeholder(v, original) for k, v in template.items()}
    if isinstance(template, list):
        return [_resolve_original_placeholder(item, original) for item in template]
    return template


# ==============================================================================
# 条件评估器
# ==============================================================================

# _CONDITION_OPS / _TYPE_IS_VALUES 从 endpoint_models 导入，避免重复定义

_SIMPLE_TYPE_MAP: dict[str, type] = {
    "string": str,
    "array": list,
    "object": dict,
}


def _evaluate_condition(body: dict[str, Any], condition: dict[str, Any]) -> bool:
    """
    评估单个条件表达式，决定规则是否应该执行。

    条件格式: {"path": "model", "op": "starts_with", "value": "claude"}

    条件无效时返回 False（跳过该规则，fail-closed）。
    """
    if not isinstance(condition, dict):
        return False

    op = condition.get("op")
    if not isinstance(op, str) or op not in _CONDITION_OPS:
        return False

    path = condition.get("path")
    if not isinstance(path, str) or not path.strip():
        return False

    found, current_val = _get_nested_value(body, path.strip())

    # 存在性检查：不需要 value
    if op == "exists":
        return found
    if op == "not_exists":
        return not found

    # 其他操作符要求字段存在
    if not found:
        return False

    expected = condition.get("value")

    # 相等/不等
    if op == "eq":
        return current_val == expected
    if op == "neq":
        return current_val != expected

    # 数值比较
    if op in ("gt", "lt", "gte", "lte"):
        if not isinstance(current_val, (int, float)) or not isinstance(expected, (int, float)):
            return False
        if op == "gt":
            return current_val > expected
        if op == "lt":
            return current_val < expected
        if op == "gte":
            return current_val >= expected
        return current_val <= expected  # lte

    # 字符串操作
    if op == "starts_with":
        return (
            isinstance(current_val, str)
            and isinstance(expected, str)
            and current_val.startswith(expected)
        )
    if op == "ends_with":
        return (
            isinstance(current_val, str)
            and isinstance(expected, str)
            and current_val.endswith(expected)
        )
    if op == "contains":
        if isinstance(current_val, str) and isinstance(expected, str):
            return expected in current_val
        if isinstance(current_val, list):
            return expected in current_val
        return False
    if op == "matches":
        if not isinstance(current_val, str) or not isinstance(expected, str):
            return False
        try:
            return re.search(expected, current_val) is not None
        except re.error:
            return False

    # 列表包含
    if op == "in":
        return isinstance(expected, list) and current_val in expected

    # 类型判断
    if op == "type_is":
        if not isinstance(expected, str) or expected not in _TYPE_IS_VALUES:
            return False
        # bool 是 int 的子类，需要特殊处理
        if expected == "number":
            return isinstance(current_val, (int, float)) and not isinstance(current_val, bool)
        if expected == "boolean":
            return isinstance(current_val, bool)
        if expected == "null":
            return current_val is None
        return isinstance(current_val, _SIMPLE_TYPE_MAP[expected])

    return False


def apply_body_rules(
    body: dict[str, Any],
    rules: list[dict[str, Any]],
    protected_keys: frozenset[str] | None = None,
) -> dict[str, Any]:
    """
    应用请求体规则

    路径语法：
    - 使用点号分隔层级：metadata.user.name
    - 转义字面量点号：config\\.v1.enabled -> key "config.v1" 下的 "enabled"
    - 使用方括号访问数组元素：messages[0].content
    - 支持多层嵌套：data[0].items[2].name
    - 支持负数索引：messages[-1]
    - 支持连续数组索引：matrix[0][1]

    支持的规则类型：
    - set: 设置/覆盖字段 {"action": "set", "path": "metadata.user_id", "value": 123}
        value 中的字符串 {{$original}} 会被替换为该路径的原值（完全匹配时保留类型）
    - drop: 删除字段 {"action": "drop", "path": "unwanted_field"}
    - rename: 重命名字段 {"action": "rename", "from": "old.key", "to": "new.key"}
    - append: 向数组追加元素 {"action": "append", "path": "messages", "value": {...}}
    - insert: 在数组指定位置插入元素 {"action": "insert", "path": "messages", "index": 0, "value": {...}}
    - regex_replace: 正则替换字符串值 {"action": "regex_replace", "path": "messages[0].content",
        "pattern": "\\bfoo\\b", "replacement": "bar", "flags": "i", "count": 0}

    Args:
        body: 原始请求体
        rules: 规则列表
        protected_keys: 受保护的字段（不能被 set/drop/rename 修改）

    Returns:
        应用规则后的请求体
    """
    if not rules:
        return body

    # 深拷贝，避免修改原始数据（尤其是嵌套 dict/list）
    result = copy.deepcopy(body)
    protected = protected_keys or PROTECTED_BODY_FIELDS
    protected_lower = frozenset(str(k).lower() for k in protected)

    for rule in rules:
        if not isinstance(rule, dict):
            continue

        # 条件触发：condition 存在且不满足时跳过规则
        condition = rule.get("condition")
        if condition is not None and not _evaluate_condition(result, condition):
            continue

        action = rule.get("action")
        if not isinstance(action, str):
            continue
        action = action.strip().lower()

        if action == "set":
            path = _extract_path(rule, protected_lower)
            if not path:
                continue
            value = rule.get("value")
            if _contains_original_placeholder(value):
                found, original = _get_nested_value(result, path)
                value = _resolve_original_placeholder(value, original if found else None)
            _set_nested_value(result, path, value)

        elif action == "drop":
            path = _extract_path(rule, protected_lower)
            if not path:
                continue
            _delete_nested_value(result, path)

        elif action == "rename":
            raw_from = rule.get("from", "")
            raw_to = rule.get("to", "")
            if not isinstance(raw_from, str) or not isinstance(raw_to, str):
                continue
            from_path = raw_from.strip()
            to_path = raw_to.strip()
            if not from_path or not to_path:
                continue
            from_parts = _parse_path(from_path)
            to_parts = _parse_path(to_path)
            if not from_parts or not to_parts:
                continue

            # 受保护字段只检查顶层 key
            if _is_protected_path(from_parts, protected_lower) or _is_protected_path(
                to_parts, protected_lower
            ):
                continue

            _rename_nested_value(result, from_path, to_path)

        elif action == "append":
            path = _extract_path(rule, protected_lower)
            if not path:
                continue
            found, target = _get_nested_value(result, path)
            if not found or not isinstance(target, list):
                continue
            target.append(rule.get("value"))

        elif action == "insert":
            path = _extract_path(rule, protected_lower)
            if not path:
                continue
            index = rule.get("index")
            if not isinstance(index, int):
                continue
            found, target = _get_nested_value(result, path)
            if not found or not isinstance(target, list):
                continue
            target.insert(index, rule.get("value"))

        elif action == "regex_replace":
            path = _extract_path(rule, protected_lower)
            if not path:
                continue
            pattern = rule.get("pattern")
            replacement = rule.get("replacement", "")
            if not isinstance(pattern, str) or not isinstance(replacement, str):
                continue
            if not pattern:
                continue

            flags_raw = rule.get("flags", "")
            re_flags = parse_re_flags(flags_raw if isinstance(flags_raw, str) else "")

            count = rule.get("count", 0)
            if not isinstance(count, int) or count < 0:
                count = 0

            found, current_val = _get_nested_value(result, path)
            if not found or not isinstance(current_val, str):
                continue

            try:
                new_val = re.compile(pattern, re_flags).sub(replacement, current_val, count=count)
                _set_nested_value(result, path, new_val)
            except re.error:
                continue  # 正则表达式无效，跳过

    return result


# ==============================================================================
# 请求构建器
# ==============================================================================


class RequestBuilder(ABC):
    """请求构建器抽象基类"""

    @abstractmethod
    def build_payload(
        self,
        original_body: dict[str, Any],
        *,
        mapped_model: str | None = None,
        is_stream: bool = False,
    ) -> dict[str, Any]:
        """构建请求体"""
        pass

    @abstractmethod
    def build_headers(
        self,
        original_headers: dict[str, str],
        endpoint: Any,
        key: Any,
        *,
        extra_headers: dict[str, str] | None = None,
        pre_computed_auth: tuple[str, str] | None = None,
    ) -> dict[str, str]:
        """构建请求头"""
        pass

    def build(
        self,
        original_body: dict[str, Any],
        original_headers: dict[str, str],
        endpoint: Any,
        key: Any,
        *,
        mapped_model: str | None = None,
        is_stream: bool = False,
        extra_headers: dict[str, str] | None = None,
        pre_computed_auth: tuple[str, str] | None = None,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """
        构建完整的请求（请求体 + 请求头）

        Args:
            original_body: 原始请求体
            original_headers: 原始请求头
            endpoint: 端点配置
            key: Provider API Key
            mapped_model: 映射后的模型名
            is_stream: 是否为流式请求
            extra_headers: 额外请求头
            pre_computed_auth: 预先计算的认证信息 (auth_header, auth_value)

        Returns:
            Tuple[payload, headers]
        """
        payload = self.build_payload(
            original_body,
            mapped_model=mapped_model,
            is_stream=is_stream,
        )

        # 应用请求体规则（如果 endpoint 配置了 body_rules）
        body_rules = getattr(endpoint, "body_rules", None)
        if body_rules:
            payload = apply_body_rules(payload, body_rules)

        headers = self.build_headers(
            original_headers,
            endpoint,
            key,
            extra_headers=extra_headers,
            pre_computed_auth=pre_computed_auth,
        )
        return payload, headers


class PassthroughRequestBuilder(RequestBuilder):
    """
    透传模式请求构建器

    适用于 CLI 等场景，尽量保持请求原样：
    - 请求体：直接复制，只修改必要字段（model, stream）
    - 请求头：清理敏感头部（黑名单），透传其他所有头部
    """

    def build_payload(
        self,
        original_body: dict[str, Any],
        *,
        mapped_model: str | None = None,  # noqa: ARG002 - 由 apply_mapped_model 处理
        is_stream: bool = False,  # noqa: ARG002 - 保留原始值，不自动添加
    ) -> dict[str, Any]:
        """
        透传请求体 - 原样复制，不做任何修改

        透传模式下：
        - model: 由各 handler 的 apply_mapped_model 方法处理
        - stream: 保留客户端原始值（不同 API 处理方式不同）
        """
        return dict(original_body)

    def build_headers(
        self,
        original_headers: dict[str, str],
        endpoint: Any,
        key: Any,
        *,
        extra_headers: dict[str, str] | None = None,
        pre_computed_auth: tuple[str, str] | None = None,
    ) -> dict[str, str]:
        """
        透传请求头 - 清理敏感头部（黑名单），透传其他所有头部

        Args:
            original_headers: 原始请求头
            endpoint: 端点配置
            key: Provider API Key
            extra_headers: 额外请求头
            pre_computed_auth: 预先计算的认证信息 (auth_header, auth_value)，
                               用于 Service Account 等异步获取 token 的场景
        """
        # 1. 根据 API 格式自动设置认证头
        if pre_computed_auth:
            # 使用预先计算的认证信息（Service Account 等场景）
            auth_header, auth_value = pre_computed_auth
        else:
            # 标准 API Key 认证
            decrypted_key = crypto_service.decrypt(key.api_key)
            raw_family = getattr(endpoint, "api_family", None)
            raw_kind = getattr(endpoint, "endpoint_kind", None)
            endpoint_sig: str | None = None
            if (
                isinstance(raw_family, str)
                and isinstance(raw_kind, str)
                and raw_family
                and raw_kind
            ):
                endpoint_sig = make_signature_key(raw_family, raw_kind)
            else:
                # 兜底：允许 endpoint.api_format 已经是 signature key 的情况
                raw_format = getattr(endpoint, "api_format", None)
                if isinstance(raw_format, str) and ":" in raw_format:
                    endpoint_sig = raw_format

            auth_header, auth_type = get_auth_config_for_endpoint(endpoint_sig or "openai:chat")
            auth_value = f"Bearer {decrypted_key}" if auth_type == "bearer" else decrypted_key
        # 认证头始终受保护，防止 header_rules 覆盖
        protected_keys = {auth_header.lower(), "content-type"}

        builder = HeaderBuilder()

        # 2. 透传原始头部（排除默认敏感头部）
        if original_headers:
            for name, value in original_headers.items():
                if name.lower() in SENSITIVE_HEADERS:
                    continue
                builder.add(name, value)

        # 3. 应用 endpoint 的请求头规则（认证头受保护，无法通过 rules 设置）
        header_rules = getattr(endpoint, "header_rules", None)
        if header_rules:
            builder.apply_rules(header_rules, protected_keys)

        # 4. 添加额外头部
        if extra_headers:
            builder.add_many(extra_headers)

        # 5. 设置认证头（最高优先级，上游始终使用 header 认证）
        builder.add(auth_header, auth_value)

        # 6. 确保有 Content-Type
        headers = builder.build()
        if not any(k.lower() == "content-type" for k in headers):
            headers["Content-Type"] = "application/json"

        return headers


# ==============================================================================
# 便捷函数
# ==============================================================================


def build_passthrough_request(
    original_body: dict[str, Any],
    original_headers: dict[str, str],
    endpoint: Any,
    key: Any,
) -> tuple[dict[str, Any], dict[str, str]]:
    """
    构建透传模式的请求

    纯透传：原样复制请求体，只处理请求头（认证等）。
    model mapping 和 stream 由调用方自行处理（不同 API 格式处理方式不同）。
    """
    builder = PassthroughRequestBuilder()
    return builder.build(
        original_body,
        original_headers,
        endpoint,
        key,
    )
