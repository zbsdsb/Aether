"""
统计数据相关数据库模型

包含: StatsBaseMixin, StatsHourly, StatsHourlyUser, StatsHourlyModel, StatsHourlyProvider,
      StatsDaily, StatsDailyModel, StatsDailyProvider, StatsDailyApiKey, StatsDailyError,
      StatsSummary, StatsUserDaily
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from ._base import Base


class StatsBaseMixin:
    """统计表公共字段 Mixin"""

    total_requests = Column(Integer, default=0, nullable=False)
    input_tokens = Column(BigInteger, default=0, nullable=False)
    output_tokens = Column(BigInteger, default=0, nullable=False)
    total_cost = Column(Float, default=0.0, nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class StatsHourly(Base):
    """小时级统计快照 - 用于时间序列查询"""

    __tablename__ = "stats_hourly"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 小时起点 (UTC)
    hour_utc = Column(DateTime(timezone=True), nullable=False, unique=True, index=True)

    # 请求统计
    total_requests = Column(Integer, default=0, nullable=False)
    success_requests = Column(Integer, default=0, nullable=False)
    error_requests = Column(Integer, default=0, nullable=False)

    # Token 统计
    input_tokens = Column(BigInteger, default=0, nullable=False)
    output_tokens = Column(BigInteger, default=0, nullable=False)
    cache_creation_tokens = Column(BigInteger, default=0, nullable=False)
    cache_read_tokens = Column(BigInteger, default=0, nullable=False)

    # 成本统计 (USD)
    total_cost = Column(Float, default=0.0, nullable=False)
    actual_total_cost = Column(Float, default=0.0, nullable=False)

    # 性能统计
    avg_response_time_ms = Column(Float, default=0.0, nullable=False)

    # 完成标记
    is_complete = Column(Boolean, default=False, nullable=False)
    aggregated_at = Column(DateTime(timezone=True), nullable=True)

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

    __table_args__ = (Index("idx_stats_hourly_hour", "hour_utc"),)


class StatsHourlyUser(StatsBaseMixin, Base):
    """小时级用户维度统计"""

    __tablename__ = "stats_hourly_user"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    hour_utc = Column(DateTime(timezone=True), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)

    success_requests = Column(Integer, default=0, nullable=False)
    error_requests = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("hour_utc", "user_id", name="uq_stats_hourly_user"),
        Index("idx_stats_hourly_user_hour", "hour_utc"),
        Index("idx_stats_hourly_user_user_hour", "user_id", "hour_utc"),
    )


class StatsHourlyModel(StatsBaseMixin, Base):
    """小时级模型维度统计"""

    __tablename__ = "stats_hourly_model"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    hour_utc = Column(DateTime(timezone=True), nullable=False, index=True)
    model = Column(String(100), nullable=False, index=True)

    avg_response_time_ms = Column(Float, default=0.0, nullable=False)

    __table_args__ = (
        UniqueConstraint("hour_utc", "model", name="uq_stats_hourly_model"),
        Index("idx_stats_hourly_model_hour", "hour_utc"),
        Index("idx_stats_hourly_model_model_hour", "model", "hour_utc"),
    )


class StatsHourlyProvider(StatsBaseMixin, Base):
    """小时级提供商维度统计"""

    __tablename__ = "stats_hourly_provider"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    hour_utc = Column(DateTime(timezone=True), nullable=False, index=True)
    provider_name = Column(String(100), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("hour_utc", "provider_name", name="uq_stats_hourly_provider"),
        Index("idx_stats_hourly_provider_hour", "hour_utc"),
    )


class StatsDaily(Base):
    """每日统计快照 - 用于快速查询历史数据"""

    __tablename__ = "stats_daily"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 统计日期 (UTC)
    date = Column(DateTime(timezone=True), nullable=False, unique=True, index=True)

    # 请求统计
    total_requests = Column(Integer, default=0, nullable=False)
    success_requests = Column(Integer, default=0, nullable=False)
    error_requests = Column(Integer, default=0, nullable=False)

    # Token 统计
    input_tokens = Column(BigInteger, default=0, nullable=False)
    output_tokens = Column(BigInteger, default=0, nullable=False)
    cache_creation_tokens = Column(BigInteger, default=0, nullable=False)
    cache_read_tokens = Column(BigInteger, default=0, nullable=False)

    # 成本统计 (USD)
    total_cost = Column(Float, default=0.0, nullable=False)
    actual_total_cost = Column(Float, default=0.0, nullable=False)  # 倍率后成本
    input_cost = Column(Float, default=0.0, nullable=False)
    output_cost = Column(Float, default=0.0, nullable=False)
    cache_creation_cost = Column(Float, default=0.0, nullable=False)
    cache_read_cost = Column(Float, default=0.0, nullable=False)

    # 性能统计
    avg_response_time_ms = Column(Float, default=0.0, nullable=False)
    p50_response_time_ms = Column(Integer, nullable=True)
    p90_response_time_ms = Column(Integer, nullable=True)
    p99_response_time_ms = Column(Integer, nullable=True)
    p50_first_byte_time_ms = Column(Integer, nullable=True)
    p90_first_byte_time_ms = Column(Integer, nullable=True)
    p99_first_byte_time_ms = Column(Integer, nullable=True)
    fallback_count = Column(Integer, default=0, nullable=False)  # Provider 切换次数

    # 使用维度统计
    unique_models = Column(Integer, default=0, server_default="0", nullable=False)
    unique_providers = Column(Integer, default=0, server_default="0", nullable=False)

    # 完成标记
    is_complete = Column(Boolean, default=False, nullable=False)
    aggregated_at = Column(DateTime(timezone=True), nullable=True)

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


class StatsDailyModel(Base):
    """每日模型统计快照 - 用于快速查询每日模型维度数据"""

    __tablename__ = "stats_daily_model"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 统计日期 (UTC)
    date = Column(DateTime(timezone=True), nullable=False, index=True)

    # 模型名称
    model = Column(String(100), nullable=False)

    # 请求统计
    total_requests = Column(Integer, default=0, nullable=False)

    # Token 统计
    input_tokens = Column(BigInteger, default=0, nullable=False)
    output_tokens = Column(BigInteger, default=0, nullable=False)
    cache_creation_tokens = Column(BigInteger, default=0, nullable=False)
    cache_read_tokens = Column(BigInteger, default=0, nullable=False)

    # 成本统计 (USD)
    total_cost = Column(Float, default=0.0, nullable=False)

    # 性能统计
    avg_response_time_ms = Column(Float, default=0.0, nullable=False)

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

    # 唯一约束：每个模型每天只有一条记录
    __table_args__ = (
        UniqueConstraint("date", "model", name="uq_stats_daily_model"),
        Index("idx_stats_daily_model_date", "date"),
        Index("idx_stats_daily_model_date_model", "date", "model"),
    )


class StatsDailyProvider(Base):
    """每日供应商统计快照 - 用于快速查询每日供应商维度数据"""

    __tablename__ = "stats_daily_provider"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 统计日期 (UTC)
    date = Column(DateTime(timezone=True), nullable=False, index=True)

    # 供应商名称
    provider_name = Column(String(100), nullable=False)

    # 请求统计
    total_requests = Column(Integer, default=0, nullable=False)

    # Token 统计
    input_tokens = Column(BigInteger, default=0, nullable=False)
    output_tokens = Column(BigInteger, default=0, nullable=False)
    cache_creation_tokens = Column(BigInteger, default=0, nullable=False)
    cache_read_tokens = Column(BigInteger, default=0, nullable=False)

    # 成本统计 (USD)
    total_cost = Column(Float, default=0.0, nullable=False)

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

    # 唯一约束：每个供应商每天只有一条记录
    __table_args__ = (
        UniqueConstraint("date", "provider_name", name="uq_stats_daily_provider"),
        Index("idx_stats_daily_provider_date", "date"),
        Index("idx_stats_daily_provider_date_provider", "date", "provider_name"),
    )


class StatsDailyApiKey(Base):
    """API Key 每日统计"""

    __tablename__ = "stats_daily_api_key"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    api_key_id = Column(String(36), ForeignKey("api_keys.id", ondelete="CASCADE"), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False, index=True)

    total_requests = Column(Integer, default=0, nullable=False)
    success_requests = Column(Integer, default=0, nullable=False)
    error_requests = Column(Integer, default=0, nullable=False)

    input_tokens = Column(BigInteger, default=0, nullable=False)
    output_tokens = Column(BigInteger, default=0, nullable=False)
    cache_creation_tokens = Column(BigInteger, default=0, nullable=False)
    cache_read_tokens = Column(BigInteger, default=0, nullable=False)

    total_cost = Column(Float, default=0.0, nullable=False)

    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("api_key_id", "date", name="uq_stats_daily_api_key"),
        Index("idx_stats_daily_api_key_date", "date"),
        Index("idx_stats_daily_api_key_key_date", "api_key_id", "date"),
        Index("idx_stats_daily_api_key_date_requests", "date", "total_requests"),
        Index("idx_stats_daily_api_key_date_cost", "date", "total_cost"),
    )

    api_key = relationship("ApiKey")


class StatsDailyError(Base):
    """每日错误统计"""

    __tablename__ = "stats_daily_error"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    error_category = Column(String(50), nullable=False)
    provider_name = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    count = Column(Integer, default=0, nullable=False)

    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "date",
            "error_category",
            "provider_name",
            "model",
            name="uq_stats_daily_error",
        ),
        Index("idx_stats_daily_error_date", "date"),
        Index("idx_stats_daily_error_category", "date", "error_category"),
    )


class StatsSummary(Base):
    """全局统计汇总 - 单行记录，存储截止到昨天的累计数据"""

    __tablename__ = "stats_summary"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 统计截止日期 (不含当天)
    cutoff_date = Column(DateTime(timezone=True), nullable=False)

    # 累计请求统计
    all_time_requests = Column(Integer, default=0, nullable=False)
    all_time_success_requests = Column(Integer, default=0, nullable=False)
    all_time_error_requests = Column(Integer, default=0, nullable=False)

    # 累计 Token 统计
    all_time_input_tokens = Column(BigInteger, default=0, nullable=False)
    all_time_output_tokens = Column(BigInteger, default=0, nullable=False)
    all_time_cache_creation_tokens = Column(BigInteger, default=0, nullable=False)
    all_time_cache_read_tokens = Column(BigInteger, default=0, nullable=False)

    # 累计成本统计 (USD)
    all_time_cost = Column(Float, default=0.0, nullable=False)
    all_time_actual_cost = Column(Float, default=0.0, nullable=False)

    # 累计用户/API Key 统计 (快照)
    total_users = Column(Integer, default=0, nullable=False)
    active_users = Column(Integer, default=0, nullable=False)
    total_api_keys = Column(Integer, default=0, nullable=False)
    active_api_keys = Column(Integer, default=0, nullable=False)

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


class StatsUserDaily(Base):
    """用户每日统计快照 - 用于用户仪表盘"""

    __tablename__ = "stats_user_daily"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 用户关联
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # 统计日期 (UTC)
    date = Column(DateTime(timezone=True), nullable=False, index=True)

    # 请求统计
    total_requests = Column(Integer, default=0, nullable=False)
    success_requests = Column(Integer, default=0, nullable=False)
    error_requests = Column(Integer, default=0, nullable=False)

    # Token 统计
    input_tokens = Column(BigInteger, default=0, nullable=False)
    output_tokens = Column(BigInteger, default=0, nullable=False)
    cache_creation_tokens = Column(BigInteger, default=0, nullable=False)
    cache_read_tokens = Column(BigInteger, default=0, nullable=False)

    # 成本统计 (USD)
    total_cost = Column(Float, default=0.0, nullable=False)

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

    # 唯一约束：每个用户每天只有一条记录
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_stats_user_daily"),
        Index("idx_stats_user_daily_user_date", "user_id", "date"),
    )

    # 关系
    user = relationship("User")
