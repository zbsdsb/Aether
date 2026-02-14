"""
认证相关数据库模型

包含: LDAPConfig, OAuthProvider, UserOAuthLink
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from ._base import Base


class LDAPConfig(Base):
    """LDAP认证配置表 - 单行配置"""

    __tablename__ = "ldap_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    server_url = Column(String(255), nullable=False)  # ldap://host:389 或 ldaps://host:636
    bind_dn = Column(Text, nullable=False)  # 绑定账号 DN（可能很长）
    bind_password_encrypted = Column(Text, nullable=True)  # 加密的绑定密码（允许 NULL 表示已清除）
    base_dn = Column(Text, nullable=False)  # 用户搜索基础 DN（可能很长）
    user_search_filter = Column(
        Text, default="(uid={username})", nullable=False
    )  # 用户搜索过滤器（可能很复杂）
    username_attr = Column(
        String(50), default="uid", nullable=False
    )  # 用户名属性 (uid/sAMAccountName)
    email_attr = Column(String(50), default="mail", nullable=False)  # 邮箱属性
    display_name_attr = Column(String(50), default="cn", nullable=False)  # 显示名称属性
    is_enabled = Column(Boolean, default=False, nullable=False)  # 是否启用 LDAP 认证
    is_exclusive = Column(
        Boolean, default=False, nullable=False
    )  # 是否仅允许 LDAP 登录（禁用本地认证）
    use_starttls = Column(Boolean, default=False, nullable=False)  # 是否使用 STARTTLS
    connect_timeout = Column(Integer, default=10, nullable=False)  # 连接超时时间（秒）

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

    def set_bind_password(self, password: str) -> None:
        """
        设置并加密绑定密码

        Args:
            password: 明文密码
        """
        from src.core.crypto import crypto_service

        self.bind_password_encrypted = crypto_service.encrypt(password)

    def get_bind_password(self) -> str:
        """
        获取解密后的绑定密码

        Returns:
            str: 解密后的明文密码

        Raises:
            DecryptionException: 解密失败时抛出异常
        """
        from src.core.crypto import crypto_service

        if not self.bind_password_encrypted:
            return ""
        return crypto_service.decrypt(self.bind_password_encrypted)


class OAuthProvider(Base):
    """OAuth Provider 配置表（按 provider_type 唯一）"""

    __tablename__ = "oauth_providers"

    # 使用 provider_type 作为主键，便于通过 URL 参数直接定位配置
    provider_type = Column(String(50), primary_key=True)
    display_name = Column(String(100), nullable=False)

    client_id = Column(Text, nullable=False)  # 某些 OAuth 提供商可能使用很长的 client_id
    client_secret_encrypted = Column(Text, nullable=True)  # 允许 NULL 表示尚未配置/已清除

    # 可选覆盖端点（需在业务层做白名单校验）
    authorization_url_override = Column(String(500), nullable=True)
    token_url_override = Column(String(500), nullable=True)
    userinfo_url_override = Column(String(500), nullable=True)

    # 可选覆盖 scopes（JSON 列表）
    scopes = Column(JSON, nullable=True)

    # 服务端控制 redirect_uri 与前端回调 URL
    redirect_uri = Column(String(500), nullable=False)
    frontend_callback_url = Column(String(500), nullable=False)

    # Provider 特定配置/映射
    attribute_mapping = Column(JSON, nullable=True)
    extra_config = Column(JSON, nullable=True)

    is_enabled = Column(Boolean, default=False, nullable=False)

    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def set_client_secret(self, secret: str) -> None:
        """设置并加密 client_secret"""
        from src.core.crypto import crypto_service

        self.client_secret_encrypted = crypto_service.encrypt(secret)

    def get_client_secret(self) -> str:
        """获取解密后的 client_secret（未配置时返回空串）"""
        from src.core.crypto import crypto_service

        if not self.client_secret_encrypted:
            return ""
        return crypto_service.decrypt(self.client_secret_encrypted)


class UserOAuthLink(Base):
    """用户与 OAuth Provider 的绑定关系"""

    __tablename__ = "user_oauth_links"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_type = Column(
        String(50),
        ForeignKey("oauth_providers.provider_type", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_user_id = Column(String(255), nullable=False)
    provider_username = Column(String(255), nullable=True)
    provider_email = Column(String(255), nullable=True)
    extra_data = Column(JSON, nullable=True)

    linked_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("provider_type", "provider_user_id", name="uq_oauth_provider_user"),
        UniqueConstraint("user_id", "provider_type", name="uq_user_oauth_provider"),
    )
