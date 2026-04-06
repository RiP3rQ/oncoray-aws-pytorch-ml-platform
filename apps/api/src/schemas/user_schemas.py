from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class BaseUserSchema(BaseModel):
    """
    Base user schema for all user schemas
    """
    email: EmailStr = Field(index=True, unique=True, nullable=False, max_length=320)


class UserRead(BaseUserSchema):
    """
    User read schema. Same as BaseUserSchema but with id and timestamps.
    """
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        nullable=False,
        sa_type=PG_UUID(as_uuid=True),
    )
    created_at: datetime = Field()
    updated_at: datetime = Field()

class UserCreate(BaseUserSchema):
    """
    User create schema. Same as BaseUserSchema but with password.
    """
    password: str = Field(min_length=8, max_length=128, nullable=False)
