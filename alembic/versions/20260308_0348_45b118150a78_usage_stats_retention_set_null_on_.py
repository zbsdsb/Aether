"""usage stats retention: SET NULL on delete and add name snapshots

Revision ID: 45b118150a78
Revises: 2d932114930d
Create Date: 2026-03-08 03:48:49.622091+00:00

"""

import sqlalchemy as sa

from alembic import op
from helpers import new_cache, replace_fk_if_needed

# revision identifiers, used by Alembic.
revision = "45b118150a78"
down_revision = "2d932114930d"
branch_labels = None
depends_on = None

_TABLES = ["usage", "stats_user_daily", "stats_daily_api_key"]


def upgrade() -> None:
    c = new_cache()
    c.load_columns(_TABLES)
    c.load_fk_rules(["stats_user_daily", "stats_daily_api_key"])

    # --- Usage: add name snapshot columns ---
    if not c.column_exists("usage", "username"):
        op.add_column(
            "usage", sa.Column("username", sa.String(100), nullable=True, comment="用户名快照")
        )
    if not c.column_exists("usage", "api_key_name"):
        op.add_column(
            "usage",
            sa.Column("api_key_name", sa.String(200), nullable=True, comment="API Key 名称快照"),
        )

    # --- StatsUserDaily: CASCADE -> SET NULL, add username snapshot ---
    replace_fk_if_needed(
        c,
        "stats_user_daily_user_id_fkey",
        "stats_user_daily",
        "users",
        ["user_id"],
        ["id"],
        "SET NULL",
    )
    op.alter_column("stats_user_daily", "user_id", existing_type=sa.String(36), nullable=True)
    if not c.column_exists("stats_user_daily", "username"):
        op.add_column(
            "stats_user_daily",
            sa.Column(
                "username",
                sa.String(100),
                nullable=True,
                comment="用户名快照（删除用户后仍可追溯）",
            ),
        )

    # --- StatsDailyApiKey: CASCADE -> SET NULL, add api_key_name snapshot ---
    replace_fk_if_needed(
        c,
        "stats_daily_api_key_api_key_id_fkey",
        "stats_daily_api_key",
        "api_keys",
        ["api_key_id"],
        ["id"],
        "SET NULL",
    )
    op.alter_column("stats_daily_api_key", "api_key_id", existing_type=sa.String(36), nullable=True)
    if not c.column_exists("stats_daily_api_key", "api_key_name"):
        op.add_column(
            "stats_daily_api_key",
            sa.Column(
                "api_key_name",
                sa.String(200),
                nullable=True,
                comment="API Key 名称快照（删除 Key 后仍可追溯）",
            ),
        )

    # --- Backfill: populate snapshots from existing FK joins ---
    # One LEFT JOIN UPDATE per table covers all rows regardless of which FK is present.
    op.execute("""
        UPDATE usage u
        SET username     = COALESCE(u.username, usr.username),
            api_key_name = COALESCE(u.api_key_name, ak.name)
        FROM usage u2
        LEFT JOIN users usr ON usr.id = u2.user_id
        LEFT JOIN api_keys ak ON ak.id = u2.api_key_id
        WHERE u.id = u2.id
          AND (u.username IS NULL OR u.api_key_name IS NULL)
    """)
    op.execute("""
        UPDATE stats_user_daily s
        SET username = usr.username
        FROM users usr
        WHERE s.user_id = usr.id AND s.username IS NULL
    """)
    op.execute("""
        UPDATE stats_daily_api_key s
        SET api_key_name = ak.name
        FROM api_keys ak
        WHERE s.api_key_id = ak.id AND s.api_key_name IS NULL
    """)


def downgrade() -> None:
    c = new_cache()
    c.load_columns(["stats_daily_api_key", "stats_user_daily", "usage"])
    c.load_fk_rules(["stats_daily_api_key", "stats_user_daily"])

    # --- Remove snapshot columns ---
    if c.column_exists("stats_daily_api_key", "api_key_name"):
        op.drop_column("stats_daily_api_key", "api_key_name")
    if c.column_exists("stats_user_daily", "username"):
        op.drop_column("stats_user_daily", "username")
    if c.column_exists("usage", "api_key_name"):
        op.drop_column("usage", "api_key_name")
    if c.column_exists("usage", "username"):
        op.drop_column("usage", "username")

    # --- StatsDailyApiKey: SET NULL -> CASCADE ---
    replace_fk_if_needed(
        c,
        "stats_daily_api_key_api_key_id_fkey",
        "stats_daily_api_key",
        "api_keys",
        ["api_key_id"],
        ["id"],
        "CASCADE",
    )
    op.alter_column(
        "stats_daily_api_key", "api_key_id", existing_type=sa.String(36), nullable=False
    )

    # --- StatsUserDaily: SET NULL -> CASCADE ---
    replace_fk_if_needed(
        c,
        "stats_user_daily_user_id_fkey",
        "stats_user_daily",
        "users",
        ["user_id"],
        ["id"],
        "CASCADE",
    )
    op.alter_column("stats_user_daily", "user_id", existing_type=sa.String(36), nullable=False)
