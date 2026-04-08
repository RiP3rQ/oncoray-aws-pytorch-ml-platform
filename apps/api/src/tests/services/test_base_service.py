"""
Tests for BaseService.
"""

import sys
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.base import BaseService


class TestBaseService:
    """Tests for BaseService."""

    def test_base_service_instantiation(self):
        """BaseService should be instantiable."""
        service = BaseService()
        assert service is not None
