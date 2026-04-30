from __future__ import annotations

import pytest

from src.intake.chest_xray_upload import (
    MAX_CHEST_XRAY_UPLOAD_BYTES,
    ChestXrayUpload,
    ChestXrayUploadPolicy,
    ChestXrayUploadTooLarge,
    ChestXrayUploadUnsupportedType,
)


class FakeUploadFile:
    def __init__(self, data: bytes, filename: str | None = "scan.png", content_type: str | None = "image/png") -> None:
        self._data = data
        self.filename = filename
        self.content_type = content_type

    async def read(self) -> bytes:
        return self._data


@pytest.mark.asyncio
async def test_chest_xray_upload_preserves_data_and_filename():
    upload = await ChestXrayUpload.from_upload_file(FakeUploadFile(b"image-data", "scan.png"))

    assert upload.data == b"image-data"
    assert upload.filename == "scan.png"


@pytest.mark.asyncio
async def test_chest_xray_upload_defaults_missing_filename():
    upload = await ChestXrayUpload.from_upload_file(FakeUploadFile(b"image-data", None))

    assert upload.filename == "upload.jpg"


@pytest.mark.asyncio
async def test_chest_xray_upload_rejects_oversized_data():
    with pytest.raises(ChestXrayUploadTooLarge) as exc_info:
        await ChestXrayUpload.from_upload_file(FakeUploadFile(b"x" * (MAX_CHEST_XRAY_UPLOAD_BYTES + 1)))

    assert exc_info.value.size_bytes == MAX_CHEST_XRAY_UPLOAD_BYTES + 1
    assert exc_info.value.max_bytes == MAX_CHEST_XRAY_UPLOAD_BYTES


@pytest.mark.asyncio
async def test_chest_xray_upload_rejects_unsupported_content_type():
    with pytest.raises(ChestXrayUploadUnsupportedType):
        await ChestXrayUpload.from_upload_file(FakeUploadFile(b"image-data", "scan.txt", "text/plain"))


@pytest.mark.asyncio
async def test_chest_xray_upload_uses_extension_when_content_type_missing():
    upload = await ChestXrayUpload.from_upload_file(FakeUploadFile(b"image-data", "scan.webp", None))

    assert upload.filename == "scan.webp"


def test_chest_xray_upload_policy_accepts_normalized_content_type():
    policy = ChestXrayUploadPolicy()

    policy.validate(size_bytes=12, content_type=" image/jpeg; charset=binary ", filename="scan.txt")


@pytest.mark.asyncio
async def test_chest_xray_upload_accepts_custom_policy():
    policy = ChestXrayUploadPolicy(
        max_bytes=4,
        accepted_content_types=frozenset({"application/dicom"}),
        accepted_extensions=frozenset({".dcm"}),
    )

    upload = await ChestXrayUpload.from_upload_file(
        FakeUploadFile(b"dicm", "scan.dcm", "application/dicom"),
        policy=policy,
    )

    assert upload.filename == "scan.dcm"


@pytest.mark.asyncio
async def test_chest_xray_upload_uses_custom_policy_size_limit():
    policy = ChestXrayUploadPolicy(max_bytes=3)

    with pytest.raises(ChestXrayUploadTooLarge) as exc_info:
        await ChestXrayUpload.from_upload_file(FakeUploadFile(b"1234"), policy=policy)

    assert exc_info.value.max_bytes == 3
