"""
Tests for S3Service - image validation and upload.
"""

import sys
from pathlib import Path

import pytest

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.s3_service import MAX_IMAGE_SIZE_BYTES, ImageSizeError, S3Service

# =============================================================================
# Tests for ImageSizeError
# =============================================================================


class TestImageSizeError:
    """Tests for ImageSizeError exception."""

    def test_image_size_error_message(self):
        """ImageSizeError should include size and max info in message."""
        error = ImageSizeError(3 * 1024 * 1024)
        assert "3145728 bytes" in str(error)
        assert "exceeds the maximum allowed size" in str(error)

    def test_image_size_error_custom_max(self):
        """ImageSizeError should accept custom max_bytes."""
        error = ImageSizeError(100, max_bytes=50)
        assert "100 bytes" in str(error)
        assert "50 bytes" in str(error)

    def test_image_size_error_attributes(self):
        """ImageSizeError should store size_bytes and max_bytes."""
        error = ImageSizeError(500)
        assert error.size_bytes == 500
        assert error.max_bytes == MAX_IMAGE_SIZE_BYTES


# =============================================================================
# Tests for S3Service.validate_image_size
# =============================================================================


class TestValidateImageSize:
    """Tests for S3Service.validate_image_size static method."""

    def test_valid_image_size_no_exception(self):
        """validate_image_size should not raise for images under 2MB."""
        S3Service.validate_image_size(b"x" * 1024)  # 1KB

    def test_valid_image_size_at_limit(self):
        """validate_image_size should not raise for images exactly at the limit."""
        S3Service.validate_image_size(b"x" * MAX_IMAGE_SIZE_BYTES)

    def test_image_size_too_large_raises_error(self):
        """validate_image_size should raise ImageSizeError for images over 2MB."""
        with pytest.raises(ImageSizeError):
            S3Service.validate_image_size(b"x" * (MAX_IMAGE_SIZE_BYTES + 1))

    def test_empty_image_is_valid(self):
        """validate_image_size should accept empty bytes."""
        S3Service.validate_image_size(b"")


# =============================================================================
# Tests for S3Service constructor
# =============================================================================


class TestS3ServiceConstructor:
    """Tests for S3Service.__init__."""

    def test_default_bucket_name(self):
        """S3Service should use default bucket name."""
        service = S3Service()
        assert service.bucket_name == "model-predictions"

    def test_custom_bucket_name(self):
        """S3Service should accept custom bucket name."""
        service = S3Service(bucket_name="custom-bucket")
        assert service.bucket_name == "custom-bucket"


# =============================================================================
# Tests for S3Service.upload_image
# =============================================================================


class TestUploadImage:
    """Tests for S3Service.upload_image."""

    @pytest.mark.asyncio
    async def test_upload_image_with_extension(self):
        """upload_image should return object key with extension."""
        service = S3Service()
        result = await service.upload_image(b"image_data", "photo.jpg")
        assert result.startswith("predictions/")
        assert result.endswith(".jpg")

    @pytest.mark.asyncio
    async def test_upload_image_without_extension(self):
        """upload_image should return object key without extension for files with no dot."""
        service = S3Service()
        result = await service.upload_image(b"image_data", "no_extension")
        assert result.startswith("predictions/")
        assert "." not in result.split("/")[-1]

    @pytest.mark.asyncio
    async def test_upload_image_oversized_raises_error(self):
        """upload_image should raise ImageSizeError for oversized images."""
        service = S3Service()
        large_data = b"x" * (MAX_IMAGE_SIZE_BYTES + 1)

        with pytest.raises(ImageSizeError):
            await service.upload_image(large_data, "large.jpg")
