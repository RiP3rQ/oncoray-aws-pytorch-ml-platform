from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import model_service_settings
from src.core.errors import ClientNotAuthorized, InvalidToken
from src.core.security import oauth2_scheme_user
from src.database.postgres import LLMModel, User
from src.database.redis import is_jti_blacklisted
from src.database.session import get_session
from src.services.model_runtime_client import ModelRuntimeClient
from src.services.model_service import ModelService
from src.services.s3_service import S3Service
from src.services.user_service import UserService
from src.utils.token_utils import decode_access_token

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
    return UserService(model=User, session=session)


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


# =============================== S3 SERVICE ===============================
def get_s3_service() -> S3Service:
    return S3Service()


S3ServiceDep = Annotated[
    S3Service,
    Depends(get_s3_service),
]

# =============================== MODEL SERVICE ===============================


def get_model_runtime_client() -> ModelRuntimeClient | None:
    if model_service_settings.MODEL_SERVICE_URL is None:
        return None

    return ModelRuntimeClient(
        base_url=model_service_settings.MODEL_SERVICE_URL,
        timeout_seconds=model_service_settings.MODEL_SERVICE_TIMEOUT_SECONDS,
    )


ModelRuntimeClientDep = Annotated[
    ModelRuntimeClient | None,
    Depends(get_model_runtime_client),
]


# Get model service
def get_model_service(
    session: SessionDep,
    s3_service: S3ServiceDep,
    model_runtime_client: ModelRuntimeClientDep,
) -> ModelService:
    """Get model service"""
    return ModelService(
        model=LLMModel,
        session=session,
        s3_service=s3_service,
        model_runtime_client=model_runtime_client,
    )


# Model service dep annotation
ModelServiceDep = Annotated[
    ModelService,
    Depends(get_model_service),
]
