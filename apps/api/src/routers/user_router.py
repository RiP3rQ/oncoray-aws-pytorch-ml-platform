from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from src.core.logger import get_logger
from src.schemas.user_schemas import UserRead, UserCreate
from src.core.dependencies import UserDep, UserServiceDep, get_user_access_token
from src.database.redis import add_jti_to_blacklist
from src.core.security import TokenData
from src.types.enums import APITag

router = APIRouter(prefix="/user", tags=[APITag.USER])
logger = get_logger(__name__)

### Register a new user
@router.post("/signup", response_model=UserRead)
async def register_user(user: UserCreate, service: UserServiceDep):
    """
    Register a new user. No token is returned as user is not verified yet.
    """
    return await service.register_user(user)


### Login a user
@router.post("/token", response_model=TokenData)
async def login_user(
    request_form: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: UserServiceDep,
):
    """
    Login a user & return the access token.
    """
    token = await service.authenticate_user_and_create_token(
        request_form.username,
        request_form.password,
    )
    return {
        "access_token": token,
        "token_type": "jwt",
    }


### Get user profile
@router.get("/me", response_model=UserRead)
async def get_user_profile(user: UserDep):
    """
    Get the user profile.
    """
    return user


### Verify User Email
@router.get("/verify", include_in_schema=False)
async def verify_user_email(token: str, service: UserServiceDep):
    """
    Verify a user email.
    """
    await service.verify_user_email(token)
    return {"detail": "Account verified"}


### Logout a user
@router.get("/logout")
async def logout_user(
    token_data: Annotated[dict, Depends(get_user_access_token)],
):
    """
    Logout a user & add the JTI to the blacklist.
    """
    await add_jti_to_blacklist(token_data["jti"])
    return {"detail": "Successfully logged out"}
