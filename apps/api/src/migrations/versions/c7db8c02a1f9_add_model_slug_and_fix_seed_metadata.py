"""add-model-slug-and-fix-seed-metadata

Revision ID: c7db8c02a1f9
Revises: 9302f10ba4a6
Create Date: 2026-04-17 13:00:00.000000

"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7db8c02a1f9"
down_revision: str | Sequence[str] | None = "9302f10ba4a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

llm_models_table = sa.table(
    "llm_models",
    sa.column("id", sa.UUID()),
    sa.column("name", sa.String(length=100)),
    sa.column("slug", sa.String(length=50)),
    sa.column("description", sa.String(length=255)),
    sa.column("version", sa.String(length=50)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

model_updates = (
    (
        UUID("11111111-1111-1111-1111-111111111111"),
        {
            "name": "ViTB16",
            "slug": "vitb16",
            "description": "Vision Transformer B/16 classifier for chest X-ray inference.",
            "version": "1.0.0",
            "updated_at": datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
        },
    ),
    (
        UUID("22222222-2222-2222-2222-222222222222"),
        {
            "name": "EffNetB0",
            "slug": "effnetb0",
            "description": "EfficientNet-B0 classifier for chest X-ray inference.",
            "version": "1.0.0",
            "updated_at": datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
        },
    ),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("llm_models", sa.Column("slug", sa.String(length=50), nullable=True))

    for model_id, values in model_updates:
        op.execute(llm_models_table.update().where(llm_models_table.c.id == model_id).values(**values))

    op.alter_column("llm_models", "slug", nullable=False)
    op.create_index(op.f("ix_llm_models_slug"), "llm_models", ["slug"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        llm_models_table.update()
        .where(llm_models_table.c.id == model_updates[0][0])
        .values(
            name="VIT optical model",
            description="Base optical model using Vision Transformer architecture.",
            version="1.0.0",
            updated_at=datetime(2026, 4, 6, 18, 0, tzinfo=UTC),
        )
    )
    op.execute(
        llm_models_table.update()
        .where(llm_models_table.c.id == model_updates[1][0])
        .values(
            name="EffectiveNetB2",
            description="Base image model using the EffectiveNetB2 architecture.",
            version="1.0.0",
            updated_at=datetime(2026, 4, 6, 18, 0, tzinfo=UTC),
        )
    )

    op.drop_index(op.f("ix_llm_models_slug"), table_name="llm_models")
    op.drop_column("llm_models", "slug")
