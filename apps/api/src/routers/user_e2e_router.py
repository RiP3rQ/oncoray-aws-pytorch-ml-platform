from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import EmailStr
from sqlalchemy import select

from src.api_types.enums import APITag
from src.core.dependencies import SessionDep
from src.database.postgres import User
from src.schemas.user_schemas import UserCreate, UserRead
from src.services.user_service import UserService

router = APIRouter(
    prefix="/user/e2e",
    tags=[APITag.USER],
    include_in_schema=False,
)


def _assert_allowed_e2e_email(email: str) -> None:
    normalized = email.lower()

    if normalized.startswith("e2e+") and normalized.endswith("@example.com"):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="E2E helper endpoints only manage e2e+...@example.com users.",
    )


@router.post("/test-user", response_model=UserRead)
async def create_or_update_test_user(
    payload: UserCreate,
    session: SessionDep,
):
    _assert_allowed_e2e_email(payload.email)

    user = await session.scalar(select(User).where(User.email == payload.email))
    password_hash = UserService._hash_password(payload.password)

    if user is None:
        user = User(
            email=payload.email,
            password_hash=password_hash,
            email_verified=True,
        )
        session.add(user)
    else:
        user.password_hash = password_hash
        user.email_verified = True

    await session.commit()
    await session.refresh(user)
    return user


@router.delete(
    "/test-user",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_test_user(
    session: SessionDep,
    email: Annotated[EmailStr, Query()],
):
    _assert_allowed_e2e_email(email)

    user = await session.scalar(select(User).where(User.email == email))
    if user is not None:
        await session.delete(user)
        await session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
