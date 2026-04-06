from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlmodel import Column, Field, Relationship, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(
        sa_column=Column(
            Uuid(as_uuid=True),
            default=uuid4,
            primary_key=True,
        )
    )
    email: str = Field(
        sa_column=Column(String(320), unique=True, index=True, nullable=False),
    )
    password_hash: str = Field(sa_column=Column(String(255), nullable=False))
    name: str = Field(sa_column=Column(String(255), nullable=False))
    email_verified: bool = Field(default=False)
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        )
    )

    session_tokens: list["SessionToken"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "lazy": "selectin",
        },
    )


class SessionToken(SQLModel, table=True):
    __tablename__ = "session_tokens"
    __table_args__ = (
        UniqueConstraint("jti_hash", name="uq_session_tokens_jti_hash"),
    )

    id: UUID = Field(
        sa_column=Column(
            Uuid(as_uuid=True),
            default=uuid4,
            primary_key=True,
        )
    )
    user_id: UUID = Field(
        sa_column=Column(
            Uuid(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    jti_hash: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        )
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    user: User = Relationship(
        back_populates="session_tokens",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
