from __future__ import annotations

from dataclasses import dataclass

from fastapi import UploadFile

MAX_CHEST_XRAY_UPLOAD_BYTES = 2 * 1024 * 1024


class ChestXrayUploadTooLarge(ValueError):
    """Raised when a Chest X-ray Upload exceeds the accepted size."""

    def __init__(
        self,
        size_bytes: int,
        max_bytes: int = MAX_CHEST_XRAY_UPLOAD_BYTES,
    ) -> None:
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes
        super().__init__(f"Image size {size_bytes} bytes exceeds the maximum allowed size of {max_bytes} bytes (2 MB).")


@dataclass(frozen=True)
class ChestXrayUpload:
    """Validated Chest X-ray Upload ready for Prediction orchestration."""

    data: bytes
    filename: str

    @classmethod
    async def from_upload_file(cls, upload_file: UploadFile) -> ChestXrayUpload:
        data = await upload_file.read()
        if len(data) > MAX_CHEST_XRAY_UPLOAD_BYTES:
            raise ChestXrayUploadTooLarge(len(data))
        return cls(data=data, filename=upload_file.filename or "upload.jpg")
