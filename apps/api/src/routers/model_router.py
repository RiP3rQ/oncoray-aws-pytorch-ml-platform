from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Path, Query, UploadFile, status

from src.core.dependencies import ModelServiceDep
from src.core.logger import get_logger
from src.schemas.model_schemas import ModelRead, PredictionResponse, UnifiedPredictionResponse
from src.services.s3_service import MAX_IMAGE_SIZE_BYTES
from src.types.enums import APITag, PredictionMode

router = APIRouter(prefix="/model", tags=[APITag.MODEL])
public_router = APIRouter(tags=[APITag.MODEL])
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# GET /model/ - list all models
# ---------------------------------------------------------------------------
@router.get("/", response_model=list[ModelRead])
async def get_all_models(service: ModelServiceDep) -> list[ModelRead]:
    """Get all models from the database."""
    logger.info("Received request to list all models")
    return await service.get_all()


# ---------------------------------------------------------------------------
# GET /model/{model_id} - get a single model by id
# ---------------------------------------------------------------------------
@router.get("/{model_id}", response_model=ModelRead)
async def get_model_by_id(
    model_id: Annotated[UUID, Path(..., description="The UUID of the model")],
    service: ModelServiceDep,
) -> ModelRead:
    """Get a model by id."""
    logger.info("Received model request for model_id=%s", model_id)
    return await service.get(model_id)


# ---------------------------------------------------------------------------
# POST /model/{model_id}/predict - internal model-service prediction
# ---------------------------------------------------------------------------
@router.post("/{model_id}/predict", response_model=PredictionResponse)
async def predict(
    model_id: Annotated[UUID, Path(..., description="The UUID of the model")],
    service: ModelServiceDep,
    image: Annotated[UploadFile, File(..., description="Image file (max 2 MB)")],
) -> PredictionResponse:
    """Run image prediction through the internal model-service."""
    logger.info("Received prediction request for model_id=%s", model_id)

    image_data = await _read_and_validate_image(image)

    return await service.predict_with_image(
        model_id=model_id,
        image_data=image_data,
        filename=image.filename or "upload.jpg",
    )


@public_router.post("/predict", response_model=UnifiedPredictionResponse)
async def predict_public(
    service: ModelServiceDep,
    model: Annotated[
        PredictionMode,
        Query(..., description="Prediction target: effnetb0, vitb16, or both."),
    ],
    image: Annotated[UploadFile, File(..., description="Image file (max 2 MB)")],
) -> UnifiedPredictionResponse:
    """Run public prediction flow against one or both model-services."""
    logger.info("Received public prediction request for mode=%s", model)
    image_data = await _read_and_validate_image(image)
    return await service.predict(
        mode=model,
        image_data=image_data,
        filename=image.filename or "upload.jpg",
    )


async def _read_and_validate_image(image: UploadFile) -> bytes:
    image_data = await image.read()

    if len(image_data) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"Image size {len(image_data)} bytes exceeds the maximum"
                f" allowed size of {MAX_IMAGE_SIZE_BYTES} bytes (2 MB)."
            ),
        )

    return image_data
