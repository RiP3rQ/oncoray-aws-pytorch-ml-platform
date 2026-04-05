from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260405_2300"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_id", "users", ["id"], unique=False)

    op.create_table(
        "session_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_session_tokens_id", "session_tokens", ["id"], unique=False)
    op.create_index("ix_session_tokens_token", "session_tokens", ["token"], unique=True)
    op.create_index("ix_session_tokens_user_id", "session_tokens", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_session_tokens_user_id", table_name="session_tokens")
    op.drop_index("ix_session_tokens_token", table_name="session_tokens")
    op.drop_index("ix_session_tokens_id", table_name="session_tokens")
    op.drop_table("session_tokens")

    op.drop_index("ix_users_id", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
