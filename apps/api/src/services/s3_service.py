from __future__ import annotations

import uuid
from io import BytesIO
from mimetypes import guess_type
from typing import Any

import boto3

from src.core.logger import get_logger
from src.intake.chest_xray_upload import ChestXrayUpload
from src.schemas.model_schemas import PredictionUploadStatus

logger = get_logger(__name__)


class S3Service:
    """
    Upload images to S3 when production mode is enabled.

    In development, mocked mode keeps tests and local flows offline.
    """

    def __init__(
        self,
        bucket_name: str = "model-predictions",
        region_name: str = "us-east-1",
        upload_mode: str = "mock",
        s3_client: Any = None,
    ) -> None:
        self.bucket_name = bucket_name
        self.region_name = region_name
        self.upload_mode = upload_mode
        self.s3_client = s3_client or (boto3.client("s3", region_name=region_name) if upload_mode == "aws" else None)

    async def upload_chest_xray(self, upload: ChestXrayUpload) -> str:
        """
        Upload a validated Chest X-ray Upload to S3 and return the object key.

        In mocked mode the key is generated but nothing is stored.
        """
        data = upload.data
        filename = upload.filename

        ext = ""
        if "." in filename:
            ext = filename.rsplit(".", 1)[-1]
        object_key = f"predictions/{uuid.uuid4()}.{ext}" if ext else f"predictions/{uuid.uuid4()}"

        if self.upload_mode == "aws":
            content_type = guess_type(filename)[0] or "application/octet-stream"
            assert self.s3_client is not None
            self.s3_client.upload_fileobj(
                Fileobj=BytesIO(data),
                Bucket=self.bucket_name,
                Key=object_key,
                ExtraArgs={"ContentType": content_type},
            )
            logger.info(
                "Uploaded image %s (%d bytes) to s3://%s/%s",
                filename,
                len(data),
                self.bucket_name,
                object_key,
            )
            return object_key

        logger.info(
            "[MOCK] Uploading image %s (%d bytes) to s3://%s/%s",
            filename,
            len(data),
            self.bucket_name,
            object_key,
        )

        return object_key

    async def persist_chest_xray_upload(self, upload: ChestXrayUpload) -> PredictionUploadStatus:
        """Persist a Chest X-ray Upload and return best-effort public status."""
        try:
            s3_key = await self.upload_chest_xray(upload)
        except Exception:
            logger.warning("Image upload failed for filename=%s", upload.filename, exc_info=True)
            return PredictionUploadStatus(status="error")

        return PredictionUploadStatus(status="ok", image_s3_key=s3_key)
