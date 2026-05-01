from fastapi import HTTPException, UploadFile, status

from src.intake.chest_xray_upload import ChestXrayUpload, ChestXrayUploadTooLarge, ChestXrayUploadUnsupportedType


async def read_chest_xray_upload(image: UploadFile) -> ChestXrayUpload:
    """Read a FastAPI upload into a validated Chest X-ray Upload."""
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
