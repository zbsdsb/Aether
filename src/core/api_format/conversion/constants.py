"""格式转换层常量定义。

将跨层共享的常量集中在 core 层，避免 core -> services 的反向依赖。
"""

from __future__ import annotations

# Thinking 签名验证的跳过标记
# 当无法获取真实签名时，使用此值作为占位符
DUMMY_THOUGHT_SIGNATURE = "skip_thought_signature_validator"
