from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import EmailStr
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class TimestampedModel(SQLModel):
    """Shared timestamp fields for database tables."""

    created_at: datetime = Field(
        default_factory=utc_now,
        nullable=False,
        sa_type=TIMESTAMP(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        nullable=False,
        sa_type=TIMESTAMP(timezone=True),
        sa_column_kwargs={"onupdate": utc_now},
    )


class User(TimestampedModel, table=True):
    """Basic user account stored in PostgreSQL."""

    __tablename__ = "users"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        nullable=False,
        sa_type=PG_UUID(as_uuid=True),
    )
    email: EmailStr = Field(index=True, unique=True, nullable=False, max_length=320)
    password_hash: str = Field(nullable=False, max_length=255)
    email_verified: bool = Field(default=False, nullable=False)


class LLMModel(TimestampedModel, table=True):
    """Minimal metadata for trainable LLM models."""

    __tablename__ = "llm_models"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        nullable=False,
        sa_type=PG_UUID(as_uuid=True),
    )
    name: str = Field(nullable=False, max_length=100, index=True)
    slug: str = Field(nullable=False, max_length=50, index=True, unique=True)
    description: str = Field(nullable=False, max_length=255)
    version: str = Field(nullable=False, max_length=50)
