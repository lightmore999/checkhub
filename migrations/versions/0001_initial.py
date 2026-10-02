"""Таблицы проверок и обращений к поставщикам

Revision ID: 0001
Revises:
Create Date: 2026-10-02
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "checks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("inn", sa.String(12), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("risk_score", sa.Integer()),
        sa.Column("risk_level", sa.String(16)),
        sa.Column("risk_factors", sa.JSON()),
        sa.Column("report", sa.JSON()),
        sa.Column("total_cost_kop", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_checks_inn", "checks", ["inn"])

    op.create_table(
        "provider_calls",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "check_id", sa.Uuid(), sa.ForeignKey("checks.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_kop", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text()),
    )
    op.create_index("ix_provider_calls_provider", "provider_calls", ["provider"])


def downgrade() -> None:
    op.drop_index("ix_provider_calls_provider", "provider_calls")
    op.drop_table("provider_calls")
    op.drop_index("ix_checks_inn", "checks")
    op.drop_table("checks")
