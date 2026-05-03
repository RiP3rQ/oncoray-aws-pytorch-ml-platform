from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api_types.enums import ModelSlug
from src.core.config import DEFAULT_MODEL_RUNTIME_TIMEOUT, model_service_settings, s3_settings
from src.core.errors import ClientNotAuthorized, InvalidToken
from src.core.security import oauth2_scheme_user
from src.database.postgres import User
from src.database.session import get_session
from src.services.model_catalog import ModelCatalog
from src.services.model_runtime_pool import ModelRuntimeAdapter, ModelRuntimePool
from src.services.model_runtime_registry import ModelRuntimeRegistry
from src.services.prediction_orchestration import ChestXrayUploadPersistence, PredictionOrchestration
from src.services.s3_service import S3Service
from src.services.user_service import UserService
from src.utils.token_utils import decode_access_token

# =============================== SESSION ===============================
# Asynchronous database session dep annotation
SessionDep = Annotated[AsyncSession, Depends(get_session)]


# Access token data dep
async def _get_access_token(token: str) -> dict[str, Any]:
    data = decode_access_token(token)

    # Validate the token
    if data is None:
        raise InvalidToken()

    return data


# User access token data
async def get_user_access_token(
    token: Annotated[str, Depends(oauth2_scheme_user)],
) -> dict[str, Any]:
    """
    Get the user access token data.
    """
    return await _get_access_token(token)


# =============================== USER SERVICE ===============================
# Logged In User
async def get_current_user(
    token_data: Annotated[dict[str, Any], Depends(get_user_access_token)],
    session: SessionDep,
) -> User:
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
def get_user_service(session: SessionDep) -> UserService:
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
    return S3Service(
        bucket_name=s3_settings.S3_BUCKET_NAME,
        region_name=s3_settings.AWS_REGION,
        upload_mode=s3_settings.S3_UPLOAD_MODE,
    )


ChestXrayUploadPersistenceDep = Annotated[
    ChestXrayUploadPersistence,
    Depends(get_s3_service),
]

# =============================== MODEL CATALOG ===============================


def get_model_runtime_adapters() -> dict[ModelSlug, ModelRuntimeAdapter]:
    registry = ModelRuntimeRegistry(
        runtime_urls=model_service_settings.model_service_urls,
        timeout_seconds=DEFAULT_MODEL_RUNTIME_TIMEOUT,
    )
    return registry.build_adapters()


ModelRuntimeAdaptersDep = Annotated[
    dict[ModelSlug, ModelRuntimeAdapter],
    Depends(get_model_runtime_adapters),
]


def get_model_runtime_pool(
    model_runtime_adapters: ModelRuntimeAdaptersDep,
) -> ModelRuntimePool:
    return ModelRuntimePool(model_runtime_adapters=model_runtime_adapters)


ModelRuntimePoolDep = Annotated[
    ModelRuntimePool,
    Depends(get_model_runtime_pool),
]


def get_model_catalog(
    session: SessionDep,
) -> ModelCatalog:
    return ModelCatalog(session=session)


ModelCatalogDep = Annotated[
    ModelCatalog,
    Depends(get_model_catalog),
]


def get_prediction_orchestration(
    upload_persistence: ChestXrayUploadPersistenceDep,
    model_runtime_pool: ModelRuntimePoolDep,
) -> PredictionOrchestration:
    return PredictionOrchestration(
        upload_persistence=upload_persistence,
        model_runtime_pool=model_runtime_pool,
    )


PredictionOrchestrationDep = Annotated[
    PredictionOrchestration,
    Depends(get_prediction_orchestration),
]
