from __future__ import annotations

import uuid
from io import BytesIO
from mimetypes import guess_type

import boto3

from src.core.logger import get_logger

logger = get_logger(__name__)

# Maximum image size: 2 MB
MAX_IMAGE_SIZE_BYTES = 2 * 1024 * 1024


class ImageSizeError(Exception):
    """Raised when an uploaded image exceeds the size limit."""

    def __init__(self, size_bytes: int, max_bytes: int = MAX_IMAGE_SIZE_BYTES):
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes
        super().__init__(f"Image size {size_bytes} bytes exceeds the maximum allowed size of {max_bytes} bytes (2 MB).")


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
        s3_client=None,
    ) -> None:
        self.bucket_name = bucket_name
        self.region_name = region_name
        self.upload_mode = upload_mode
        self.s3_client = s3_client or (boto3.client("s3", region_name=region_name) if upload_mode == "aws" else None)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @staticmethod
    def validate_image_size(data: bytes) -> None:
        """Raise ``ImageSizeError`` when *data* exceeds 2 MB."""
        if len(data) > MAX_IMAGE_SIZE_BYTES:
            raise ImageSizeError(len(data))

    async def upload_image(self, data: bytes, filename: str) -> str:
        """
        Upload *data* to S3 and return the object key.

        In mocked mode the key is generated but nothing is stored.

        Parameters
        ----------
        data:
            Raw image bytes.
        filename:
            Original filename (used for extension extraction).

        Returns
        -------
        str
            The S3 object key that *would* be used.
        """
        self.validate_image_size(data)

        # Build a unique object key preserving the original extension
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
