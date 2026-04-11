"""seed-model-table

Revision ID: 9302f10ba4a6
Revises: 9b9040153d5d
Create Date: 2026-04-06 19:15:37.527229

"""
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9302f10ba4a6'
down_revision: str | Sequence[str] | None = '9b9040153d5d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

llm_models_table = sa.table(
    "llm_models",
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
    sa.column("id", sa.UUID()),
    sa.column("name", sa.String(length=100)),
    sa.column("description", sa.String(length=255)),
    sa.column("version", sa.String(length=50)),
)

seeded_model_ids = (
    UUID("11111111-1111-1111-1111-111111111111"),
    UUID("22222222-2222-2222-2222-222222222222"),
)

seeded_models = [
    {
        "created_at": datetime(2026, 4, 6, 18, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 4, 6, 18, 0, tzinfo=UTC),
        "id": seeded_model_ids[0],
        "name": "VIT optical model",
        "description": "Base optical model using Vision Transformer architecture.",
        "version": "1.0.0",
    },
    {
        "created_at": datetime(2026, 4, 6, 18, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 4, 6, 18, 0, tzinfo=UTC),
        "id": seeded_model_ids[1],
        "name": "EffectiveNetB2",
        "description": "Base image model using the EffectiveNetB2 architecture.",
        "version": "1.0.0",
    },
]


def upgrade() -> None:
    """Upgrade schema."""
    op.bulk_insert(llm_models_table, seeded_models)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        sa.delete(llm_models_table).where(
            llm_models_table.c.id.in_(seeded_model_ids)
        )
    )
