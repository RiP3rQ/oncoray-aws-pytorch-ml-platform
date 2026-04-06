from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import EmailStr
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Column, Field, Relationship, SQLModel, select

class User(SQLModel):
    name: str

    email: EmailStr
    email_verified: bool = Field(default=False)
    password_hash: str = Field(exclude=True)