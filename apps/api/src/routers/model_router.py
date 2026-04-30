from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Path, Query, UploadFile, status

from src.core.dependencies import ModelCatalogDep, PredictionOrchestrationDep
from src.core.logger import get_logger
from src.intake.chest_xray_upload import ChestXrayUpload, ChestXrayUploadTooLarge, ChestXrayUploadUnsupportedType
from src.schemas.model_schemas import ModelRead, UnifiedPredictionResponse
from src.types.enums import APITag, PredictionMode

router = APIRouter(prefix="/model", tags=[APITag.MODEL])
public_router = APIRouter(tags=[APITag.MODEL])
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# GET /model/ - list all models
# ---------------------------------------------------------------------------
@router.get("/", response_model=list[ModelRead])
async def list_model_catalog(catalog: ModelCatalogDep) -> list[ModelRead]:
    """List Model Catalog items."""
    logger.info("Received request to list Model Catalog")
    return await catalog.list_models()


# ---------------------------------------------------------------------------
# GET /model/{model_id} - get a single model by id
# ---------------------------------------------------------------------------
@router.get("/{model_id}", response_model=ModelRead)
async def get_model_catalog_item(
    model_id: Annotated[UUID, Path(..., description="The UUID of the model")],
    catalog: ModelCatalogDep,
) -> ModelRead:
    """Get a Model Catalog item by id."""
    logger.info("Received Model Catalog request for model_id=%s", model_id)
    return await catalog.get_model(model_id)


@public_router.post("/predict", response_model=UnifiedPredictionResponse)
async def predict_public(
    orchestration: PredictionOrchestrationDep,
    model: Annotated[
        PredictionMode,
        Query(..., description="Prediction target: effnetb0, vitb16, or both."),
    ],
    image: Annotated[UploadFile, File(..., description="Image file (max 2 MB)")],
) -> UnifiedPredictionResponse:
    """Run public prediction flow against one or both model-services."""
    logger.info("Received public prediction request for mode=%s", model)
    upload = await _read_chest_xray_upload(image)
    return await orchestration.predict(
        mode=model,
        upload=upload,
    )


async def _read_chest_xray_upload(image: UploadFile) -> ChestXrayUpload:
    try:
        return await ChestXrayUpload.from_upload_file(image)
    except ChestXrayUploadTooLarge as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except ChestXrayUploadUnsupportedType as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
