"""
Tests for S3Service - image validation and upload.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.intake.chest_xray_upload import ChestXrayUpload
from src.services.s3_service import S3Service


@pytest.fixture
def chest_xray_upload():
    return ChestXrayUpload(data=b"image_data", filename="photo.jpg")


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

    def test_aws_mode_uses_injected_client(self):
        """AWS mode should preserve injected client for production uploads."""
        client = Mock()
        service = S3Service(bucket_name="custom-bucket", upload_mode="aws", s3_client=client)
        assert service.upload_mode == "aws"
        assert service.s3_client is client


# =============================================================================
# Tests for S3Service.upload_chest_xray
# =============================================================================


class TestUploadChestXray:
    """Tests for S3Service.upload_chest_xray."""

    @pytest.mark.asyncio
    async def test_upload_chest_xray_with_extension(self, chest_xray_upload):
        """upload_chest_xray should return object key with extension."""
        service = S3Service()
        result = await service.upload_chest_xray(chest_xray_upload)
        assert result.startswith("predictions/")
        assert result.endswith(".jpg")

    @pytest.mark.asyncio
    async def test_upload_chest_xray_without_extension(self):
        """upload_chest_xray should return key without extension for no-dot files."""
        service = S3Service()
        result = await service.upload_chest_xray(ChestXrayUpload(data=b"image_data", filename="no_extension"))
        assert result.startswith("predictions/")
        assert "." not in result.split("/")[-1]

    @pytest.mark.asyncio
    async def test_upload_chest_xray_in_aws_mode_calls_s3(self, chest_xray_upload):
        """AWS mode should upload through boto3 client."""
        client = Mock()
        service = S3Service(
            bucket_name="prod-bucket",
            region_name="eu-central-1",
            upload_mode="aws",
            s3_client=client,
        )

        result = await service.upload_chest_xray(chest_xray_upload)

        assert result.startswith("predictions/")
        client.upload_fileobj.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_upload_access_puts_and_heads_verification_object(self):
        """verify_upload_access should exercise production S3 write and read permissions."""
        client = Mock()
        service = S3Service(
            bucket_name="prod-bucket",
            region_name="eu-central-1",
            upload_mode="aws",
            s3_client=client,
        )

        result = await service.verify_upload_access()

        assert result.startswith("predictions/verification/")
        assert result.endswith(".txt")
        client.put_object.assert_called_once()
        client.head_object.assert_called_once_with(Bucket="prod-bucket", Key=result)

    @pytest.mark.asyncio
    async def test_verify_upload_access_requires_aws_mode(self):
        """verify_upload_access should fail before deployment when mock mode is still active."""
        service = S3Service(upload_mode="mock")

        with pytest.raises(RuntimeError, match="S3_UPLOAD_MODE='aws'"):
            await service.verify_upload_access()

    @pytest.mark.asyncio
    async def test_persist_chest_xray_upload_returns_ok_status(self, chest_xray_upload):
        """persist_chest_xray_upload should return public upload status."""
        service = S3Service()

        result = await service.persist_chest_xray_upload(chest_xray_upload)

        assert result.status == "ok"
        assert result.image_s3_key is not None
        assert result.image_s3_key.startswith("predictions/")

    @pytest.mark.asyncio
    async def test_persist_chest_xray_upload_returns_error_status_on_failure(self, chest_xray_upload):
        """persist_chest_xray_upload should keep upload persistence best-effort."""
        client = Mock()
        client.upload_fileobj.side_effect = RuntimeError("s3 down")
        service = S3Service(upload_mode="aws", s3_client=client)

        result = await service.persist_chest_xray_upload(chest_xray_upload)

        assert result.status == "error"
        assert result.image_s3_key is None
