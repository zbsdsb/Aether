"""add provider_import_tasks table

Revision ID: e4f5a6b7c8d9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-05 17:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4f5a6b7c8d9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if table_exists("provider_import_tasks"):
        return

    op.create_table(
        "provider_import_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("provider_id", sa.String(length=36), nullable=False),
        sa.Column("endpoint_id", sa.String(length=36), nullable=True),
        sa.Column("task_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("source_kind", sa.String(length=30), nullable=False, server_default="all_in_hub"),
        sa.Column("source_id", sa.String(length=120), nullable=False),
        sa.Column("source_name", sa.String(length=100), nullable=False),
        sa.Column("source_origin", sa.String(length=500), nullable=False),
        sa.Column("credential_payload", sa.Text(), nullable=False),
        sa.Column("source_metadata", sa.JSON(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["endpoint_id"], ["provider_endpoints.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_id",
            "task_type",
            "source_id",
            name="uq_provider_import_tasks_provider_task_source",
        ),
    )
    op.create_index(
        "ix_provider_import_tasks_provider_id",
        "provider_import_tasks",
        ["provider_id"],
        unique=False,
    )
    op.create_index(
        "idx_provider_import_tasks_status",
        "provider_import_tasks",
        ["status"],
        unique=False,
    )
    op.create_index(
        "idx_provider_import_tasks_provider_status",
        "provider_import_tasks",
        ["provider_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    if not table_exists("provider_import_tasks"):
        return

    op.drop_index("idx_provider_import_tasks_provider_status", table_name="provider_import_tasks")
    op.drop_index("idx_provider_import_tasks_status", table_name="provider_import_tasks")
    op.drop_index("ix_provider_import_tasks_provider_id", table_name="provider_import_tasks")
    op.drop_table("provider_import_tasks")
