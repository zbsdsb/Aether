"""add first_byte_time_ms to usage table

Revision ID: 180e63a9c83a
Revises: e9b3d63f0cbf
Create Date: 2025-12-15 17:07:44.631032+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '180e63a9c83a'
down_revision = 'e9b3d63f0cbf'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """应用迁移：升级到新版本"""
    # 添加首字时间字段到 usage 表
    op.add_column('usage', sa.Column('first_byte_time_ms', sa.Integer(), nullable=True))


def downgrade() -> None:
    """回滚迁移：降级到旧版本"""
    # 删除首字时间字段
    op.drop_column('usage', 'first_byte_time_ms')
