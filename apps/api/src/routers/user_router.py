from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from src.api_types.enums import APITag
from src.core.dependencies import UserDep, UserServiceDep, get_user_access_token
from src.core.logger import get_logger
from src.core.security import TokenData
from src.schemas.user_schemas import UserCreate, UserRead

router = APIRouter(prefix="/user", tags=[APITag.USER])
logger = get_logger(__name__)


### Register a new user
@router.post("/signup", response_model=UserRead)
async def register_user(user: UserCreate, service: UserServiceDep) -> UserRead:
    """
    Register a new user. No token is returned as user is not verified yet.
    """
    return UserRead.model_validate(await service.register_user(user), from_attributes=True)


### Login a user
@router.post("/token", response_model=TokenData)
async def login_user(
    request_form: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: UserServiceDep,
) -> TokenData:
    """
    Login a user & return the access token.
    """
    token = await service.authenticate_user_and_create_token(
        request_form.username,
        request_form.password,
    )
    return TokenData(access_token=token, token_type="jwt")


### Get user profile
@router.get("/me", response_model=UserRead)
async def get_user_profile(user: UserDep) -> UserRead:
    """
    Get the user profile.
    """
    return UserRead.model_validate(user, from_attributes=True)


### Verify User Email
@router.get("/verify", include_in_schema=False)
async def verify_user_email(token: str, service: UserServiceDep) -> dict[str, str]:
    """
    Verify a user email.
    """
    await service.verify_user_email(token)
    return {"detail": "Account verified"}


### Logout a user
@router.get("/logout")
async def logout_user(
    _token_data: Annotated[dict[str, Any], Depends(get_user_access_token)],
) -> dict[str, str]:
    """
    Confirm the current access token is valid.

    Session cleanup is client-owned; the frontend removes stored JWTs.
    """
    return {"detail": "Successfully logged out"}
