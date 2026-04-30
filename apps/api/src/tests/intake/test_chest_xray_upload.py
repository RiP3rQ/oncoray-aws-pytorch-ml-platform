from __future__ import annotations

import pytest

from src.intake.chest_xray_upload import (
    MAX_CHEST_XRAY_UPLOAD_BYTES,
    ChestXrayUpload,
    ChestXrayUploadTooLarge,
)


class FakeUploadFile:
    def __init__(self, data: bytes, filename: str | None = "scan.png") -> None:
        self._data = data
        self.filename = filename

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
