"""
杂项数据库模型

包含: SystemConfig, VideoTask, Announcement, AnnouncementRead, AuditEventType, AuditLog,
      GeminiFileMapping, _generate_short_id
"""

from __future__ import annotations

import secrets
import string
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from ._base import Base


class SystemConfig(Base):
    """系统配置表"""

    __tablename__ = "system_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(JSON, nullable=False)
    description = Column(Text, nullable=True)

    # 时间戳
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


def _generate_short_id(length: int = 12) -> str:
    """生成 Gemini 风格的短 ID（小写字母+数字）"""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class VideoTask(Base):
    """视频生成任务"""

    __tablename__ = "video_tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Gemini 风格的短 ID，用于对外暴露（如 operations/xxx）
    short_id = Column(String(16), unique=True, index=True, default=_generate_short_id)
    request_id = Column(
        String(100), unique=True, index=True, nullable=False
    )  # 关联 Usage/RequestCandidate
    external_task_id = Column(String(200))

    # 关联
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    api_key_id = Column(String(36), ForeignKey("api_keys.id"))
    provider_id = Column(String(36), ForeignKey("providers.id"))
    endpoint_id = Column(String(36), ForeignKey("provider_endpoints.id"))
    key_id = Column(String(36), ForeignKey("provider_api_keys.id"))

    # 格式转换追踪
    client_api_format = Column(String(50), nullable=False)
    provider_api_format = Column(String(50), nullable=False)
    format_converted = Column(Boolean, default=False)

    # 任务配置
    model = Column(String(100), nullable=False)
    prompt = Column(Text, nullable=False)
    original_request_body = Column(JSON)
    converted_request_body = Column(JSON)

    # 视频参数 (统一内部格式)
    duration_seconds = Column(Integer, default=4)
    resolution = Column(String(20), default="720p")
    aspect_ratio = Column(String(10), default="16:9")
    size = Column(String(20))

    # 状态
    status = Column(String(20), default="pending")
    progress_percent = Column(Integer, default=0)
    progress_message = Column(String(500))

    # 结果
    video_url = Column(String(2000))
    video_urls = Column(JSON)
    thumbnail_url = Column(String(2000))
    video_size_bytes = Column(BigInteger)
    video_duration_seconds = Column(Float)  # 实际视频时长（秒）
    video_expires_at = Column(DateTime(timezone=True))

    # 存储 (可选)
    stored_video_path = Column(String(500))
    storage_provider = Column(String(50))

    # 错误
    error_code = Column(String(50))
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # 轮询配置
    poll_interval_seconds = Column(Integer, default=10)
    next_poll_at = Column(DateTime(timezone=True))  # 索引在 __table_args__ 中定义
    poll_count = Column(Integer, default=0)
    max_poll_count = Column(Integer, default=360)

    # Remix 支持
    remixed_from_task_id = Column(
        String(36), ForeignKey("video_tasks.id", ondelete="SET NULL"), nullable=True
    )

    # 使用追踪（候选 key、请求头等）
    request_metadata = Column(JSON, nullable=True)  # 存储候选 key 列表、请求头等追踪信息
    # 示例: {
    #   "candidate_keys": [{"key_id": "xxx", "endpoint_id": "yyy", "priority": 1}, ...],
    #   "selected_key_index": 0,
    #   "client_ip": "1.2.3.4",
    #   "user_agent": "...",
    #   "request_headers": {...}
    # }

    # 时间戳
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    submitted_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 关系
    user = relationship("User", backref="video_tasks")
    remixed_from = relationship("VideoTask", remote_side=[id], backref="remixes")

    # 复合索引和唯一约束
    __table_args__ = (
        Index("idx_video_tasks_user_status", "user_id", "status"),
        Index("idx_video_tasks_next_poll", "next_poll_at"),
        Index("idx_video_tasks_external_id", "external_task_id"),
        UniqueConstraint("user_id", "external_task_id", name="uq_video_tasks_user_external_id"),
    )


class Announcement(Base):
    """公告表"""

    __tablename__ = "announcements"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)  # 支持 Markdown
    type = Column(String(20), default="info")  # info, warning, maintenance, important
    priority = Column(Integer, default=0)  # 优先级,数字越大越重要

    # 发布信息
    author_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    is_pinned = Column(Boolean, default=False)  # 置顶

    # 时间范围
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)

    # 时间戳
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 关系
    author = relationship("User", back_populates="authored_announcements")
    reads = relationship(
        "AnnouncementRead", back_populates="announcement", cascade="all, delete-orphan"
    )


class AnnouncementRead(Base):
    """公告已读记录表"""

    __tablename__ = "announcement_reads"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    announcement_id = Column(String(36), ForeignKey("announcements.id"), nullable=False)
    read_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # 唯一约束
    __table_args__ = (UniqueConstraint("user_id", "announcement_id", name="uq_user_announcement"),)

    # 关系
    user = relationship("User", back_populates="announcement_reads")
    announcement = relationship("Announcement", back_populates="reads")


class AuditEventType(PyEnum):
    """审计事件类型"""

    # 认证相关
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    API_KEY_CREATED = "api_key_created"
    API_KEY_DELETED = "api_key_deleted"
    API_KEY_USED = "api_key_used"

    # 请求相关
    REQUEST_SUCCESS = "request_success"
    REQUEST_FAILED = "request_failed"
    REQUEST_RATE_LIMITED = "request_rate_limited"
    REQUEST_QUOTA_EXCEEDED = "request_quota_exceeded"

    # 管理操作
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    PROVIDER_ADDED = "provider_added"
    PROVIDER_UPDATED = "provider_updated"
    PROVIDER_REMOVED = "provider_removed"

    # 安全事件
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DATA_EXPORT = "data_export"
    CONFIG_CHANGED = "config_changed"

    # Management Token 相关
    MANAGEMENT_TOKEN_CREATED = "management_token_created"
    MANAGEMENT_TOKEN_UPDATED = "management_token_updated"
    MANAGEMENT_TOKEN_DELETED = "management_token_deleted"
    MANAGEMENT_TOKEN_USED = "management_token_used"
    MANAGEMENT_TOKEN_EXPIRED = "management_token_expired"
    MANAGEMENT_TOKEN_IP_BLOCKED = "management_token_ip_blocked"


class AuditLog(Base):
    """审计日志模型"""

    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    event_type = Column(String(50), nullable=False, index=True)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    api_key_id = Column(String(36), nullable=True)

    # 事件详情
    description = Column(Text, nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    request_id = Column(String(100), nullable=True, index=True)

    # 相关数据
    event_metadata = Column(JSON, nullable=True)

    # 响应信息
    status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # 时间戳
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # 关系
    user = relationship("User", back_populates="audit_logs")


class GeminiFileMapping(Base):
    """
    Gemini Files API 文件与 Provider Key 的映射关系

    用于持久化存储 file_id -> key_id 的绑定关系，
    确保后续 generateContent 请求使用上传时的同一 Key。

    Gemini 文件有 48 小时有效期，此表中的记录也会在过期后被清理。
    """

    __tablename__ = "gemini_file_mappings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)

    # 文件名（如 files/abc123xyz）
    file_name = Column(String(255), nullable=False, unique=True, index=True)

    # Provider Key ID（关联到 provider_api_keys 表）
    key_id = Column(
        String(36),
        ForeignKey("provider_api_keys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 用户 ID（用于权限验证，可选）
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # 文件元数据（可选，用于调试）
    display_name = Column(String(255), nullable=True)
    mime_type = Column(String(100), nullable=True)

    # 源文件哈希（用于关联相同源文件的不同上传，可选）
    # 当同一源文件上传到多个 Key 时，可通过此字段找到所有等效文件
    source_hash = Column(String(64), nullable=True, index=True)

    # 时间戳
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    # 过期时间（Gemini 文件 48 小时后过期）
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # 关系
    key = relationship("ProviderAPIKey")
    user = relationship("User")

    __table_args__ = (
        Index("idx_gemini_file_mappings_expires", "expires_at"),
        Index("idx_gemini_file_mappings_source_hash", "source_hash"),
    )
