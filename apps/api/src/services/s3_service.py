from __future__ import annotations

import uuid
from io import BytesIO

from src.core.logger import get_logger

logger = get_logger(__name__)

# Maximum image size: 2 MB
MAX_IMAGE_SIZE_BYTES = 2 * 1024 * 1024


class ImageSizeError(Exception):
    """Raised when an uploaded image exceeds the size limit."""

    def __init__(self, size_bytes: int, max_bytes: int = MAX_IMAGE_SIZE_BYTES):
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes
        super().__init__(
            f"Image size {size_bytes} bytes exceeds the maximum allowed size of {max_bytes} bytes (2 MB)."
        )


class S3Service:
    """
    Placeholder S3 service for uploading images.

    Currently this is a mocked implementation.  When the real bucket is ready,
    uncomment the boto3 calls and provide credentials via environment
    variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION,
    S3_BUCKET_NAME).
    """

    def __init__(self, bucket_name: str = "model-predictions") -> None:
        self.bucket_name = bucket_name
        # TODO: Uncomment when real S3 is configured
        # import boto3
        # self.s3_client = boto3.client("s3")

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

        In mocked mode the key is generated but nothing is actually stored.

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
        object_key = (
            f"predictions/{uuid.uuid4()}.{ext}"
            if ext
            else f"predictions/{uuid.uuid4()}"
        )

        logger.info(
            "[MOCK] Uploading image %s (%d bytes) to s3://%s/%s",
            filename,
            len(data),
            self.bucket_name,
            object_key,
        )

        # TODO: Uncomment when real S3 is configured
        # self.s3_client.put_object(
        #     Bucket=self.bucket_name,
        #     Key=object_key,
        #     Body=BytesIO(data),
        #     ContentType=f"image/{ext}" if ext else "application/octet-stream",
        # )

        return object_key
