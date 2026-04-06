from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession


from src.services.model_service import ModelService
from src.services.user_service import UserService
from src.core.errors import ClientNotAuthorized, InvalidToken
from src.database.session import get_session
from src.database.redis import is_jti_blacklisted
from src.utils.token_utils import decode_access_token
from src.core.security import oauth2_scheme_user
from src.database.postgres import User

# =============================== SESSION ===============================
# Asynchronous database session dep annotation
SessionDep = Annotated[AsyncSession, Depends(get_session)]

# Access token data dep
async def _get_access_token(token: str) -> dict:
    data = decode_access_token(token)

    # Validate the token
    if data is None or await is_jti_blacklisted(data["jti"]):
        raise InvalidToken()

    return data


# User access token data
async def get_user_access_token(
    token: Annotated[str, Depends(oauth2_scheme_user)],
) -> dict:
    """
    Get the user access token data.
    """
    return await _get_access_token(token)

# =============================== USER SERVICE ===============================
# Logged In User
async def get_current_user(
    token_data: Annotated[dict, Depends(get_user_access_token)],
    session: SessionDep,
):
    """
    Get the logged in user.
    """
    current_user = await session.get(
        User,
        UUID(token_data["user"]["id"]),
    )

    if current_user is None:
        raise ClientNotAuthorized()

    return current_user

# User service dep
def get_user_service(session: SessionDep):
    return UserService(User, session)

# User dep annotation
UserDep = Annotated[
    User,
    Depends(get_current_user),
]

# User service dep annotation
UserServiceDep = Annotated[
    UserService,
    Depends(get_user_service),
]

# =============================== MODEL SERVICE ===============================

# Get model service
async def get_model_service() -> ModelService:
    """Get model service"""
    return ModelService()

# Model service dep annotation
ModelServiceDep = Annotated[
    ModelService,
    Depends(get_model_service),
]
