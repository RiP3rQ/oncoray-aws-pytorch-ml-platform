from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.api.enums.tags import APITag
from app.core.security import TokenData
from app.database.redis import add_jti_to_blacklist
from app.services.user import UserService

from ..dependencies import get_current_user, get_user_access_token
from ..schemas.user import UserCreate, UserResponse

router = APIRouter(prefix="/user", tags=[APITag.USER])


### Register a new user
@router.post("/signup", response_model=UserResponse)
async def register_user(user: UserCreate, service: UserService):
    return await service.add(user)


### Login a user
@router.post("/token", response_model=TokenData)
async def login_user(
    request_form: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: UserService,
):
    token = await service.token(request_form.username, request_form.password)
    return {
        "access_token": token,
        "token_type": "jwt",
    }


### Get user profile
@router.get("/me", response_model=UserResponse)
async def get_user_profile(user: Annotated[UserResponse, Depends(get_current_user)]):
    return user



### Verify User Email
@router.get("/verify", include_in_schema=False)
async def verify_user_email(token: str, service: UserService):
    await service.verify_email(token)
    return {"detail": "Account verified"}


### Logout a user
@router.get("/logout")
async def logout_user(
    token_data: Annotated[dict, Depends(get_user_access_token)],
):
    await add_jti_to_blacklist(token_data["jti"])
    return {"detail": "Successfully logged out"}