from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="Email used as the unique login identifier.")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Plain-text password that will be hashed with bcrypt before storage.",
    )


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Registered email address.")
    password: str = Field(..., min_length=8, max_length=128, description="Plain-text account password.")


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    created_at: datetime


class LoginResponse(BaseModel):
    access_token: str = Field(..., description="Opaque bearer token for authenticating subsequent requests.")
    token_type: str = Field(default="bearer", description="Authentication scheme for the access token.")
    user: UserResponse
