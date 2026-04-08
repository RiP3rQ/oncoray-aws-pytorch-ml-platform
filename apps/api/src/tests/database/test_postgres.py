"""
Tests for PostgreSQL models (User, LLMModel, TimestampedModel).
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.postgres import utc_now, TimestampedModel, User, LLMModel


# =============================================================================
# Tests for utc_now
# =============================================================================


class TestUtcNow:
    """Tests for utc_now helper."""

    def test_utc_now_returns_datetime_with_timezone(self):
        """utc_now should return timezone-aware UTC datetime."""
        result = utc_now()
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_utc_now_returns_utc(self):
        """utc_now should return UTC timezone."""
        result = utc_now()
        assert result.tzinfo == timezone.utc


# =============================================================================
# Tests for TimestampedModel
# =============================================================================


class TestTimestampedModel:
    """Tests for TimestampedModel."""

    def test_timestamped_model_has_created_at(self):
        """TimestampedModel should have created_at field."""
        assert "created_at" in TimestampedModel.model_fields

    def test_timestamped_model_has_updated_at(self):
        """TimestampedModel should have updated_at field."""
        assert "updated_at" in TimestampedModel.model_fields


# =============================================================================
# Tests for User model
# =============================================================================


class TestUserModel:
    """Tests for User model."""

    def test_user_table_name(self):
        """User model should have table name 'users'."""
        assert User.__tablename__ == "users"

    def test_user_has_email_field(self):
        """User model should have email field."""
        assert "email" in User.model_fields

    def test_user_has_password_hash_field(self):
        """User model should have password_hash field."""
        assert "password_hash" in User.model_fields

    def test_user_has_email_verified_field(self):
        """User model should have email_verified field."""
        assert "email_verified" in User.model_fields

    def test_user_has_id_field(self):
        """User model should have id field."""
        assert "id" in User.model_fields

    def test_user_is_timestamped(self):
        """User should inherit from TimestampedModel."""
        assert issubclass(User, TimestampedModel)


# =============================================================================
# Tests for LLMModel
# =============================================================================


class TestLLMModelModel:
    """Tests for LLMModel model."""

    def test_llm_model_table_name(self):
        """LLMModel should have table name 'llm_models'."""
        assert LLMModel.__tablename__ == "llm_models"

    def test_llm_model_has_name_field(self):
        """LLMModel should have name field."""
        assert "name" in LLMModel.model_fields

    def test_llm_model_has_description_field(self):
        """LLMModel should have description field."""
        assert "description" in LLMModel.model_fields

    def test_llm_model_has_version_field(self):
        """LLMModel should have version field."""
        assert "version" in LLMModel.model_fields

    def test_llm_model_has_id_field(self):
        """LLMModel should have id field."""
        assert "id" in LLMModel.model_fields

    def test_llm_model_is_timestamped(self):
        """LLMModel should inherit from TimestampedModel."""
        assert issubclass(LLMModel, TimestampedModel)
