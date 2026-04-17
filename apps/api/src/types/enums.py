from enum import StrEnum


class APITag(StrEnum):
    """API Tags for the Core API"""

    MODEL = "Model"
    USER = "User"


class ModelSlug(StrEnum):
    """Stable slugs for supported visual inference models."""

    EFFNETB0 = "effnetb0"
    VITB16 = "vitb16"


class PredictionMode(StrEnum):
    """Valid query modes for public prediction API."""

    EFFNETB0 = ModelSlug.EFFNETB0.value
    VITB16 = ModelSlug.VITB16.value
    BOTH = "both"
