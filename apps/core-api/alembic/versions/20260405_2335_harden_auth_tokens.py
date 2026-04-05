from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260405_2335"
down_revision = "20260405_2300"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "password_hash",
            existing_type=sa.String(length=128),
            type_=sa.String(length=255),
            existing_nullable=False,
        )

    with op.batch_alter_table("session_tokens") as batch_op:
        batch_op.add_column(sa.Column("jti_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))

    # Existing opaque tokens cannot be transformed into JWT identifiers, so they are invalidated here.
    op.execute(sa.text("DELETE FROM session_tokens"))

    with op.batch_alter_table("session_tokens") as batch_op:
        batch_op.alter_column(
            "jti_hash",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        batch_op.alter_column(
            "expires_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch_op.drop_index("ix_session_tokens_token")
        batch_op.create_index("ix_session_tokens_jti_hash", ["jti_hash"], unique=True)
        batch_op.create_index("ix_session_tokens_expires_at", ["expires_at"], unique=False)
        batch_op.drop_column("token")


def downgrade() -> None:
    with op.batch_alter_table("session_tokens") as batch_op:
        batch_op.add_column(sa.Column("token", sa.String(length=128), nullable=True))
        batch_op.drop_index("ix_session_tokens_expires_at")
        batch_op.drop_index("ix_session_tokens_jti_hash")
        batch_op.create_index("ix_session_tokens_token", ["token"], unique=True)
        batch_op.drop_column("expires_at")
        batch_op.drop_column("jti_hash")

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "password_hash",
            existing_type=sa.String(length=255),
            type_=sa.String(length=128),
            existing_nullable=False,
        )
