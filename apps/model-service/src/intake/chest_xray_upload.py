from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

MAX_CHEST_XRAY_UPLOAD_BYTES = 2 * 1024 * 1024
ACCEPTED_CHEST_XRAY_UPLOAD_CONTENT_TYPES = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/webp",
    }
)
ACCEPTED_CHEST_XRAY_UPLOAD_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})


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


class ChestXrayUploadUnsupportedType(ValueError):
    """Raised when a Chest X-ray Upload is not an accepted image type."""

    def __init__(self, content_type: str | None, filename: str) -> None:
        self.content_type = content_type
        self.filename = filename
        super().__init__("Chest X-ray Upload must be a PNG, JPG, or WEBP image.")


@dataclass(frozen=True)
class ChestXrayUpload:
    """Validated Chest X-ray Upload ready for Model Runtime scoring."""

    data: bytes
    filename: str

    @classmethod
    async def from_upload_file(cls, upload_file: UploadFile) -> ChestXrayUpload:
        data = await upload_file.read()
        if len(data) > MAX_CHEST_XRAY_UPLOAD_BYTES:
            raise ChestXrayUploadTooLarge(len(data))

        filename = upload_file.filename or "upload.jpg"
        content_type = upload_file.content_type
        if not _is_supported_image_type(content_type=content_type, filename=filename):
            raise ChestXrayUploadUnsupportedType(content_type=content_type, filename=filename)

        return cls(data=data, filename=filename)


def _is_supported_image_type(content_type: str | None, filename: str) -> bool:
    normalized_content_type = content_type.lower().split(";", 1)[0].strip() if content_type else None
    if normalized_content_type:
        return normalized_content_type in ACCEPTED_CHEST_XRAY_UPLOAD_CONTENT_TYPES
    return Path(filename).suffix.lower() in ACCEPTED_CHEST_XRAY_UPLOAD_EXTENSIONS
