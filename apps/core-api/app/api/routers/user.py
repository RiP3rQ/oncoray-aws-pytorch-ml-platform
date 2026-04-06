from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from pydantic import EmailStr

from app.api.schemas.shipment import ShipmentRead
from app.api.enums.tags import APITag
from app.core.security import TokenData
from app.database.redis import add_jti_to_blacklist
from app.utils import TEMPLATE_DIR
from app.config import app_settings

from ..dependencies import UserDep, UserServiceDep, get_user_access_token
from ..schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/user", tags=[APITag.USER])


### Register a new seller
@router.post("/signup", response_model=UserRead)
async def register_seller(user: UserCreate, service: UserServiceDep):
    return await service.add(user)


### Login a user
@router.post("/token", response_model=TokenData)
async def login_user(
    request_form: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: UserServiceDep,
):
    token = await service.token(request_form.username, request_form.password)
    return {
        "access_token": token,
        "token_type": "jwt",
    }


### Get user profile
@router.get("/me", response_model=UserRead)
async def get_user_profile(user: UserDep):
    return user



### Verify User Email
@router.get("/verify", include_in_schema=False)
async def verify_user_email(token: str, service: UserServiceDep):
    await service.verify_email(token)
    return {"detail": "Account verified"}


### Logout a seller
@router.get("/logout")
async def logout_seller(
    token_data: Annotated[dict, Depends(get_user_access_token)],
):
    await add_jti_to_blacklist(token_data["jti"])
    return {"detail": "Successfully logged out"}