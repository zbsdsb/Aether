"""
SQLAlchemy Base 声明基类

所有数据库模型子模块从此文件导入 Base，确保全局唯一。
直接复用 database.py 的 Base，避免出现两套 MetaData 实例。
"""

from src.models.database import Base

__all__ = ["Base"]
