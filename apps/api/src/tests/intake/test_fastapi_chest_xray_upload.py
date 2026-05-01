from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.intake.fastapi_chest_xray_upload import read_chest_xray_upload


class FakeUploadFile:
    def __init__(self, data: bytes, filename: str | None = "scan.png", content_type: str | None = "image/png") -> None:
        self._data = data
        self.filename = filename
        self.content_type = content_type

    async def read(self) -> bytes:
        return self._data


@pytest.mark.asyncio
async def test_read_chest_xray_upload_returns_validated_upload() -> None:
    upload = await read_chest_xray_upload(FakeUploadFile(b"image-data", "scan.png", "image/png"))

    assert upload.data == b"image-data"
    assert upload.filename == "scan.png"


@pytest.mark.asyncio
async def test_read_chest_xray_upload_maps_unsupported_type_to_http_415() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await read_chest_xray_upload(FakeUploadFile(b"not-image", "notes.txt", "text/plain"))

    assert exc_info.value.status_code == 415


@pytest.mark.asyncio
async def test_read_chest_xray_upload_maps_oversized_upload_to_http_413() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await read_chest_xray_upload(FakeUploadFile(b"x" * (2 * 1024 * 1024 + 1), "scan.png", "image/png"))

    assert exc_info.value.status_code == 413
