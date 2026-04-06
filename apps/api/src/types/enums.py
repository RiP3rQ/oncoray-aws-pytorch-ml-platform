from enum import Enum

class APITag(str, Enum):
    """API Tags for the Core API"""
    MODEL = "Model"
    USER = "User"