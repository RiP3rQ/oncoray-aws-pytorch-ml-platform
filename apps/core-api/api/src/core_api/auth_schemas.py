from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(..., description="Email used as the unique login identifier.")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Plain-text password that will be hashed with bcrypt before storage.",
    )


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(..., description="Registered email address.")
    password: str = Field(..., min_length=8, max_length=128, description="Plain-text account password.")


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    created_at: datetime


class LoginResponse(BaseModel):
    access_token: str = Field(..., description="Signed JWT bearer token for authenticating subsequent requests.")
    token_type: Literal["bearer"] = Field(default="bearer", description="Authentication scheme for the access token.")
    expires_at: datetime = Field(..., description="UTC timestamp at which the access token expires.")
    user: UserResponse
