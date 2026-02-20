"""Add provider_request_body and client_response_body columns to usage table

Revision ID: 7e8f9a0b1c2d
Revises: 6d7e8f9a0b1c
Create Date: 2026-02-20 18:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7e8f9a0b1c2d"
down_revision: str | None = "6d7e8f9a0b1c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_columns = {col["name"] for col in inspector.get_columns("usage")}

    if "provider_request_body" not in existing_columns:
        op.add_column("usage", sa.Column("provider_request_body", sa.JSON(), nullable=True))
    if "provider_request_body_compressed" not in existing_columns:
        op.add_column(
            "usage", sa.Column("provider_request_body_compressed", sa.LargeBinary(), nullable=True)
        )
    if "client_response_body" not in existing_columns:
        op.add_column("usage", sa.Column("client_response_body", sa.JSON(), nullable=True))
    if "client_response_body_compressed" not in existing_columns:
        op.add_column(
            "usage", sa.Column("client_response_body_compressed", sa.LargeBinary(), nullable=True)
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_columns = {col["name"] for col in inspector.get_columns("usage")}

    for col in (
        "client_response_body_compressed",
        "client_response_body",
        "provider_request_body_compressed",
        "provider_request_body",
    ):
        if col in existing_columns:
            op.drop_column("usage", col)
