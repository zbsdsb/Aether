"""
用户相关数据库模型

包含: User, ApiKey, UserQuota, UserPreference, ManagementToken
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from src.config import config
from src.core.enums import AuthSource, UserRole

from ._base import Base


class User(Base):
    """用户模型"""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    # OAuth 用户可能没有邮箱；Postgres unique 允许多个 NULL
    email = Column(String(255), unique=True, index=True, nullable=True)
    # 注意：所有创建用户的入口必须显式写入 true/false，禁止依赖默认值
    email_verified = Column(Boolean, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    # OAuth 用户可能没有本地密码（v1 仅做字段兼容）
    password_hash = Column(String(255), nullable=True)
    role = Column(
        Enum(
            UserRole,
            name="userrole",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=UserRole.USER,
        nullable=False,
    )
    auth_source = Column(
        Enum(
            AuthSource,
            name="authsource",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=AuthSource.LOCAL,
        nullable=False,
    )

    # LDAP 标识（仅 auth_source=ldap 时使用，用于在邮箱变更/用户名冲突时稳定关联本地账户）
    ldap_dn = Column(String(512), nullable=True, index=True)
    ldap_username = Column(String(255), nullable=True, index=True)

    # 访问限制（NULL 表示不限制，允许访问所有资源）
    allowed_providers = Column(JSON, nullable=True)  # 允许使用的提供商 ID 列表
    allowed_api_formats = Column(JSON, nullable=True)  # 允许使用的 API 格式列表
    allowed_models = Column(JSON, nullable=True)  # 允许使用的模型名称列表

    # Key 能力配置
    model_capability_settings = Column(JSON, nullable=True)  # 用户针对特定模型的能力配置
    # 示例: {"claude-sonnet-4-20250514": {"cache_1h": true}}

    # 配额管理
    quota_usd = Column(Float, nullable=True)  # 美元配额(NULL 表示无限制)
    used_usd = Column(Float, default=0.0)  # 当前周期已使用美元
    total_usd = Column(Float, default=0.0)  # 累积消费总额

    # 状态
    is_active = Column(Boolean, default=True, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)

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
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # 关系 - CASCADE delete: 让数据库处理级联删除
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    management_tokens = relationship(
        "ManagementToken", back_populates="user", cascade="all, delete-orphan"
    )
    preferences = relationship(
        "UserPreference", back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    quotas = relationship(
        "UserQuota", back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    announcement_reads = relationship(
        "AnnouncementRead",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # 关系 - SET NULL: 保留历史记录，让数据库处理 SET NULL
    usage_records = relationship("Usage", back_populates="user", passive_deletes=True)
    authored_announcements = relationship(
        "Announcement",
        back_populates="author",
        foreign_keys="Announcement.author_id",
        passive_deletes=True,
    )
    audit_logs = relationship("AuditLog", back_populates="user", passive_deletes=True)

    def set_password(self, password: str) -> None:
        """设置密码"""
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode(
            "utf-8"
        )

    def verify_password(self, password: str) -> bool:
        """验证密码"""
        if not self.password_hash:
            return False
        return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))


class ApiKey(Base):
    """API密钥模型"""

    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    key_hash = Column(String(64), unique=True, index=True, nullable=False)  # API密钥的SHA256哈希
    key_encrypted = Column(Text, nullable=True)  # 加密后的完整密钥，用于查看
    name = Column(String(100), nullable=True)  # 密钥名称，便于用户管理

    # 使用统计
    total_requests = Column(Integer, default=0)
    total_cost_usd = Column(Float, default=0.0)

    # 余额管理（仅用于独立余额 Key）
    balance_used_usd = Column(Float, default=0.0)  # 已使用余额（USD），用于统计
    current_balance_usd = Column(Float, nullable=True)  # 当前余额（USD），NULL 表示无限制
    is_standalone = Column(
        Boolean, default=False, nullable=False
    )  # 是否为独立余额 Key（给非注册用户使用）

    # 访问限制（NULL 表示不限制，允许访问所有资源）
    allowed_providers = Column(JSON, nullable=True)  # 允许使用的提供商 ID 列表
    allowed_api_formats = Column(JSON, nullable=True)  # 允许使用的 API 格式列表
    allowed_models = Column(JSON, nullable=True)  # 允许使用的模型名称列表
    rate_limit = Column(Integer, default=None, nullable=True)  # 每分钟请求限制，None = 无限制
    concurrent_limit = Column(Integer, default=5, nullable=True)  # 并发请求限制

    # Key 能力配置
    force_capabilities = Column(JSON, nullable=True)  # 强制开启的能力
    # 示例: {"cache_1h": true} - 强制所有支持的模型都用 1h 缓存

    # 状态
    is_active = Column(Boolean, default=True, nullable=False)
    is_locked = Column(Boolean, default=False, nullable=False)  # 管理员锁定，用户无法使用/操作
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # 过期时间
    auto_delete_on_expiry = Column(Boolean, default=False, nullable=False)  # 过期后是否自动删除

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

    # 关系
    user = relationship("User", back_populates="api_keys")
    usage_records = relationship("Usage", back_populates="api_key")
    provider_mappings = relationship(
        "ApiKeyProviderMapping", back_populates="api_key", cascade="all, delete-orphan"
    )

    @staticmethod
    def generate_key() -> str:
        """生成API密钥（使用加密安全的随机数生成器）"""
        import string

        # 只使用字母和数字，避免特殊字符
        alphabet = string.ascii_letters + string.digits
        random_part = "".join(secrets.choice(alphabet) for _ in range(32))
        return f"{config.api_key_prefix}-{random_part}"

    @staticmethod
    def hash_key(api_key: str) -> str:
        """对API密钥进行哈希"""
        return hashlib.sha256(api_key.encode()).hexdigest()

    def set_key(self, api_key: str) -> None:
        """
        设置API密钥(用于测试和数据初始化)

        Args:
            api_key: 明文API密钥

        注意: 此方法会设置 key_hash 和 key_encrypted
        """
        from src.core.crypto import crypto_service

        # 设置哈希(用于验证)
        self.key_hash = self.hash_key(api_key)

        # 设置加密的完整密钥(用于显示和管理)
        self.key_encrypted = crypto_service.encrypt(api_key)

    def verify_key(self, api_key: str) -> bool:
        """
        验证API密钥是否匹配(用于测试)

        Args:
            api_key: 明文API密钥

        Returns:
            bool: 密钥是否匹配
        """
        return self.key_hash == self.hash_key(api_key)

    def get_display_key(self) -> str:
        """获取用于显示的脱敏密钥（前缀...后4位）"""
        from src.core.crypto import crypto_service

        if self.key_encrypted:
            try:
                # 使用静默模式，避免在显示场景打印错误日志
                full_key = crypto_service.decrypt(self.key_encrypted, silent=True)
                # 格式：sk-SpJ3y...sdf4
                prefix = full_key[:10] if len(full_key) >= 10 else full_key[: len(full_key) // 2]
                suffix = full_key[-4:] if len(full_key) >= 4 else ""
                return f"{prefix}...{suffix}"
            except Exception:
                pass
        # 降级：无法解密时返回占位符
        return "sk-****"


class UserQuota(Base):
    """用户配额历史记录"""

    __tablename__ = "user_quotas"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # 配额类型
    quota_type = Column(String(50), nullable=False)  # monthly, daily, custom

    # 配额值
    quota_usd = Column(Float, nullable=False)

    # 时间范围
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)

    # 使用情况
    used_usd = Column(Float, default=0.0)

    # 状态
    is_active = Column(Boolean, default=True)

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

    # 关系
    user = relationship("User", back_populates="quotas")


class UserPreference(Base):
    """用户偏好设置表"""

    __tablename__ = "user_preferences"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # 个人信息
    avatar_url = Column(String(500), nullable=True)  # 头像URL
    bio = Column(Text, nullable=True)  # 个人简介

    # 偏好设置
    default_provider_id = Column(String(36), ForeignKey("providers.id"), nullable=True)
    theme = Column(String(20), default="light")  # light/dark/auto
    language = Column(String(10), default="zh-CN")
    timezone = Column(String(50), default="Asia/Shanghai")

    # 通知设置
    email_notifications = Column(Boolean, default=True)
    usage_alerts = Column(Boolean, default=True)
    announcement_notifications = Column(Boolean, default=True)

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

    # 关系
    user = relationship("User", back_populates="preferences")
    default_provider = relationship("Provider")


class ManagementToken(Base):
    """Management Token 模型 - 用于程序化管理 API 调用"""

    __tablename__ = "management_tokens"

    # Token 格式常量
    TOKEN_PREFIX = "ae_"
    TOKEN_RANDOM_LENGTH = 40

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Token 信息
    token_hash = Column(String(64), unique=True, index=True, nullable=False)  # SHA256 哈希
    token_prefix = Column(String(12), nullable=True)  # Token 前缀用于显示（如 ae_xxxxxxxx）
    name = Column(String(100), nullable=False)  # Token 名称
    description = Column(Text, nullable=True)  # 描述

    # IP 白名单（可选）
    allowed_ips = Column(JSON, nullable=True)  # 允许的 IP 列表，NULL = 不限制
    # 格式: ["192.168.1.1", "10.0.0.0/24"]

    # 有效期
    expires_at = Column(DateTime(timezone=True), nullable=True)  # NULL = 永不过期

    # 使用统计
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    last_used_ip = Column(String(45), nullable=True)
    usage_count = Column(Integer, default=0)  # 使用次数

    # 状态
    is_active = Column(Boolean, default=True, nullable=False)

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

    # 关系
    user = relationship("User", back_populates="management_tokens")

    # 索引和约束
    __table_args__ = (
        Index("idx_management_tokens_user_id", "user_id"),
        Index("idx_management_tokens_is_active", "is_active"),
        UniqueConstraint("user_id", "name", name="uq_management_tokens_user_name"),
        # IP 白名单必须为 NULL（不限制）或非空数组，禁止空数组
        # 注意：JSON 类型的 NULL 可能被序列化为 JSON 'null'，需要同时处理
        CheckConstraint(
            "allowed_ips IS NULL OR allowed_ips::text = 'null' OR json_array_length(allowed_ips) > 0",
            name="check_allowed_ips_not_empty",
        ),
    )

    @staticmethod
    def generate_token() -> str:
        """生成 Management Token（使用加密安全的随机数）"""
        import string

        alphabet = string.ascii_letters + string.digits
        random_part = "".join(
            secrets.choice(alphabet) for _ in range(ManagementToken.TOKEN_RANDOM_LENGTH)
        )
        return f"{ManagementToken.TOKEN_PREFIX}{random_part}"

    @staticmethod
    def hash_token(token: str) -> str:
        """对 Token 进行 SHA256 哈希

        安全性说明（当前方案是安全的）：
        - Token 熵为 62^40（约 2^238），暴力破解在计算上不可行
        - 结合速率限制（默认 30 次/分钟/IP），在线攻击不可行
        - 不需要盐值：盐值用于防止彩虹表攻击，但 Token 是高熵随机值，
          不存在可预计算的"常见值"，因此彩虹表攻击不适用
        """
        return hashlib.sha256(token.encode()).hexdigest()

    def set_token(self, token: str) -> None:
        """设置 Token（只存储哈希和前缀用于显示）"""
        self.token_hash = self.hash_token(token)
        # 存储前缀用于显示（ae_ + 4 个字符，共 7 个字符）
        self.token_prefix = token[:7] if len(token) > 7 else token

    def get_display_token(self) -> str:
        """获取用于显示的脱敏 Token（显示前缀 + 掩码）"""
        if self.token_prefix:
            return f"{self.token_prefix}...****"
        return "ae_****"

    def is_ip_allowed(self, client_ip: str) -> bool:
        """检查 IP 是否在白名单中

        安全策略：
        - None 或不设置表示不限制（允许所有 IP）
        - 非空列表表示只允许列表中的 IP
        - 无效的白名单条目会被记录并跳过
        - 无效的客户端 IP 直接拒绝
        - 支持 IPv4 映射的 IPv6 地址规范化
        """
        if self.allowed_ips is None:
            return True  # 未设置白名单，不限制

        import ipaddress

        from src.core.logger import logger

        # 防御性检查：空列表应该在数据库层被拒绝，但这里再检查一次
        if not self.allowed_ips:
            logger.critical(f"Management Token {self.id} - allowed_ips 为空列表（违反数据库约束）")
            return False  # fail-safe

        def normalize_ip(ip_str: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
            """规范化 IP 地址，将 IPv4 映射的 IPv6 转换为 IPv4"""
            try:
                ip = ipaddress.ip_address(ip_str)
                if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
                    return ip.ipv4_mapped
                return ip
            except ValueError:
                return None

        # 规范化客户端 IP
        client = normalize_ip(client_ip)
        if client is None:
            logger.error(f"Management Token {self.id} - 拒绝无效的客户端 IP: {client_ip}")
            return False

        valid_entries = 0
        for allowed in self.allowed_ips:
            try:
                if "/" in allowed:
                    # CIDR 格式
                    network = ipaddress.ip_network(allowed, strict=False)
                    valid_entries += 1
                    if client in network:
                        return True
                else:
                    # 精确 IP
                    allowed_ip = normalize_ip(allowed)
                    if allowed_ip is None:
                        logger.error(f"Management Token {self.id} - 白名单包含无效条目: {allowed}")
                        continue
                    valid_entries += 1
                    if client == allowed_ip:
                        return True
            except ValueError:
                logger.error(f"Management Token {self.id} - 白名单包含无效条目: {allowed}")
                continue

        # 如果白名单全部无效，记录严重错误并拒绝
        if valid_entries == 0:
            logger.critical(f"Management Token {self.id} - 白名单全部无效，拒绝所有访问")

        return False

    @property
    def is_expired(self) -> bool:
        """检查 Token 是否已过期（时区安全）"""
        if not self.expires_at:
            return False

        expires = self.expires_at
        if expires.tzinfo is None:
            # 数据库中的时间应该有时区信息，如果没有则表示数据完整性问题
            from src.core.logger import logger

            logger.error(f"Management Token {self.id} expires_at 缺少时区信息（数据完整性问题）")
            expires = expires.replace(tzinfo=timezone.utc)

        return expires < datetime.now(timezone.utc)
