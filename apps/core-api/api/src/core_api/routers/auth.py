from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select

from core_api.auth import generate_session_token, hash_password, verify_password
from core_api.auth_schemas import LoginRequest, LoginResponse, RegisterRequest, UserResponse
from core_api.deps import DbSession, get_current_session
from core_api.models import SessionToken, User


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new account using an email address and password.",
    responses={
        status.HTTP_201_CREATED: {"description": "The user account was created successfully."},
        status.HTTP_409_CONFLICT: {"description": "A user with the given email already exists."},
    },
)
def register(payload: RegisterRequest, db: DbSession) -> UserResponse:
    existing_user = db.scalar(select(User).where(User.email == payload.email))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    user = User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Log in with email and password",
    description="Validate the provided credentials and issue a bearer token for the session.",
    responses={
        status.HTTP_200_OK: {"description": "The user was authenticated successfully."},
        status.HTTP_401_UNAUTHORIZED: {"description": "The provided email or password is invalid."},
    },
)
def login(payload: LoginRequest, db: DbSession) -> LoginResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    session_token = SessionToken(user_id=user.id, token=generate_session_token())
    db.add(session_token)
    db.commit()
    return LoginResponse(access_token=session_token.token, user=UserResponse.model_validate(user))


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out the current session",
    description="Invalidate the bearer token used to authenticate the current request.",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "The current session was logged out successfully."},
        status.HTTP_401_UNAUTHORIZED: {"description": "The bearer token is missing, invalid, or expired."},
    },
)
def logout(
    db: DbSession,
    session_token: Annotated[SessionToken, Depends(get_current_session)],
) -> Response:
    db.delete(session_token)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
