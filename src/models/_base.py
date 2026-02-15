"""
SQLAlchemy Base 声明基类

所有数据库模型子模块从此文件导入 Base，确保全局唯一。
直接复用 database.py 的 Base，避免出现两套 MetaData 实例。
"""

from __future__ import annotations

from enum import Enum
from typing import Any, ClassVar

from src.models.database import Base


class ExportMixin:
    """配置导出 Mixin -- 基于排除列表自动收集字段。

    子类定义 ``_export_exclude`` 列出不需要导出的列名（如 id、外键、
    运行时状态、时间戳等），``to_export_dict()`` 会自动收集其余所有列。

    新增数据库列时无需修改导出代码，只有确认不需要导出的列才需要
    加入 ``_export_exclude``。
    """

    # 子类覆盖：不导出的列名集合
    _export_exclude: ClassVar[frozenset[str]] = frozenset()

    def to_export_dict(self) -> dict[str, Any]:
        """将模型实例转为可导出的字典（排除 _export_exclude 中的字段）。"""
        result: dict[str, Any] = {}
        for col in self.__table__.columns:  # type: ignore[attr-defined]
            if col.name in self._export_exclude:
                continue
            value = getattr(self, col.name)
            if isinstance(value, Enum):
                value = value.value
            result[col.name] = value
        return result

    @classmethod
    def get_export_fields(cls) -> frozenset[str]:
        """返回可导出字段名集合（用于测试验证导入代码覆盖率）。"""
        return frozenset(
            col.name
            for col in cls.__table__.columns  # type: ignore[attr-defined]
            if col.name not in cls._export_exclude
        )


__all__ = ["Base", "ExportMixin"]
