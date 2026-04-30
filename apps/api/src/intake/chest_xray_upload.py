from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from fastapi import UploadFile

DEFAULT_MAX_CHEST_XRAY_UPLOAD_BYTES = 2 * 1024 * 1024
DEFAULT_ACCEPTED_CHEST_XRAY_UPLOAD_CONTENT_TYPES = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/webp",
    }
)
DEFAULT_ACCEPTED_CHEST_XRAY_UPLOAD_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})


class ChestXrayUploadTooLarge(ValueError):
    """Raised when a Chest X-ray Upload exceeds the accepted size."""

    def __init__(
        self,
        size_bytes: int,
        max_bytes: int = DEFAULT_MAX_CHEST_XRAY_UPLOAD_BYTES,
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
class ChestXrayUploadPolicy:
    """Validation policy for a Chest X-ray Upload."""

    max_bytes: int = DEFAULT_MAX_CHEST_XRAY_UPLOAD_BYTES
    accepted_content_types: frozenset[str] = field(
        default_factory=lambda: DEFAULT_ACCEPTED_CHEST_XRAY_UPLOAD_CONTENT_TYPES
    )
    accepted_extensions: frozenset[str] = field(default_factory=lambda: DEFAULT_ACCEPTED_CHEST_XRAY_UPLOAD_EXTENSIONS)

    def validate(self, *, size_bytes: int, content_type: str | None, filename: str) -> None:
        if size_bytes > self.max_bytes:
            raise ChestXrayUploadTooLarge(size_bytes, self.max_bytes)
        if not self.is_supported_image_type(content_type=content_type, filename=filename):
            raise ChestXrayUploadUnsupportedType(content_type=content_type, filename=filename)

    def is_supported_image_type(self, *, content_type: str | None, filename: str) -> bool:
        normalized_content_type = content_type.lower().split(";", 1)[0].strip() if content_type else None
        if normalized_content_type:
            return normalized_content_type in self.accepted_content_types
        return Path(filename).suffix.lower() in self.accepted_extensions


DEFAULT_CHEST_XRAY_UPLOAD_POLICY = ChestXrayUploadPolicy()
MAX_CHEST_XRAY_UPLOAD_BYTES = DEFAULT_CHEST_XRAY_UPLOAD_POLICY.max_bytes
ACCEPTED_CHEST_XRAY_UPLOAD_CONTENT_TYPES = DEFAULT_CHEST_XRAY_UPLOAD_POLICY.accepted_content_types
ACCEPTED_CHEST_XRAY_UPLOAD_EXTENSIONS = DEFAULT_CHEST_XRAY_UPLOAD_POLICY.accepted_extensions


@dataclass(frozen=True)
class ChestXrayUpload:
    """Validated Chest X-ray Upload ready for Prediction orchestration."""

    data: bytes
    filename: str

    @classmethod
    async def from_upload_file(
        cls,
        upload_file: UploadFile,
        policy: ChestXrayUploadPolicy = DEFAULT_CHEST_XRAY_UPLOAD_POLICY,
    ) -> ChestXrayUpload:
        data = await upload_file.read()
        filename = upload_file.filename or "upload.jpg"
        policy.validate(size_bytes=len(data), content_type=upload_file.content_type, filename=filename)

        return cls(data=data, filename=filename)
