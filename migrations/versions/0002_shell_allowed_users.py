"""Add shell allowlist table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_shell_allowed_users"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shell_allowed_users",
        sa.Column("user_id", sa.BigInteger(), primary_key=True),
        sa.Column("added_by", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("shell_allowed_users")

