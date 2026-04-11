"""
Tests for core configuration settings.
"""

import sys
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import (
    AppSettings,
    DatabaseSettings,
    NotificationSettings,
    S3Settings,
    SecuritySettings,
    app_settings,
    db_settings,
    normalize_database_url,
    notification_settings,
    s3_settings,
    security_settings,
    to_sync_database_url,
)

# =============================================================================
# Tests for AppSettings
# =============================================================================


class TestAppSettings:
    """Tests for AppSettings configuration."""

    def test_app_settings_defaults(self):
        """AppSettings should have correct default values."""
        settings = AppSettings()
        assert settings.APP_HTTP_PROTOCOL == "http"
        assert settings.APP_NAME == "Core API"
        assert settings.APP_ENVIRONMENT == "development"
        assert settings.APP_LOG_LEVEL == "INFO"
        assert settings.ACCESS_TOKEN_TTL_MINUTES == 15
        assert settings.APP_DOMAIN == "localhost:8000"

    def test_normalize_app_log_level(self):
        """AppSettings should normalize log level to uppercase."""
        settings = AppSettings(APP_LOG_LEVEL="debug")
        assert settings.APP_LOG_LEVEL == "DEBUG"

    def test_cors_allowed_origins_tuple(self):
        """cors_allowed_origins_tuple should split CORS_ALLOWED_ORIGINS."""
        settings = AppSettings(
            CORS_ALLOWED_ORIGINS="http://localhost:3000,http://localhost:5173"
        )
        origins = settings.cors_allowed_origins_tuple
        assert "http://localhost:3000" in origins
        assert "http://localhost:5173" in origins

    def test_cors_allowed_origins_strips_whitespace(self):
        """cors_allowed_origins_tuple should strip whitespace."""
        settings = AppSettings(CORS_ALLOWED_ORIGINS="  http://a.com , http://b.com  ")
        origins = settings.cors_allowed_origins_tuple
        assert "http://a.com" in origins
        assert "http://b.com" in origins

    def test_cors_allowed_origins_empty_entries_filtered(self):
        """cors_allowed_origins_tuple should filter out empty entries."""
        settings = AppSettings(CORS_ALLOWED_ORIGINS="http://a.com,,http://b.com,,,,")
        origins = settings.cors_allowed_origins_tuple
        assert len(origins) == 2


# =============================================================================
# Tests for DatabaseSettings
# =============================================================================


class TestDatabaseSettings:
    """Tests for DatabaseSettings configuration."""

    def test_database_settings_defaults(self):
        """DatabaseSettings should have correct default values."""
        settings = DatabaseSettings()
        assert settings.POSTGRES_SERVER == "localhost"
        assert settings.POSTGRES_PORT == 5433
        assert settings.POSTGRES_USER == "postgres"
        assert settings.POSTGRES_DB == "pytorch-model"

    def test_postgres_url_with_override(self):
        """POSTGRES_URL should use CORE_API_DATABASE_URL when set."""
        settings = DatabaseSettings(
            CORE_API_DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db"
        )
        url = settings.POSTGRES_URL
        assert url == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_postgres_url_default(self):
        """POSTGRES_URL should construct from components when CORE_API_DATABASE_URL is not set."""
        settings = DatabaseSettings()
        url = settings.POSTGRES_URL
        assert "postgresql+asyncpg://" in url
        assert settings.POSTGRES_USER in url
        assert str(settings.POSTGRES_PORT) in url

    def test_sync_postgres_url(self):
        """SYNC_POSTGRES_URL should convert async URL to sync."""
        settings = DatabaseSettings(
            CORE_API_DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db"
        )
        sync_url = settings.SYNC_POSTGRES_URL
        assert "postgresql://" in sync_url
        assert "asyncpg" not in sync_url

    def test_redis_url(self):
        """REDIS_URL should construct Redis URL correctly."""
        settings = DatabaseSettings()
        url = settings.REDIS_URL(0)
        assert url.startswith("redis://")
        assert ":6379/0" in url


# =============================================================================
# Tests for SecuritySettings
# =============================================================================


class TestSecuritySettings:
    """Tests for SecuritySettings configuration."""

    def test_security_settings_defaults(self):
        """SecuritySettings should have correct default values."""
        settings = SecuritySettings()
        assert settings.SECRET_KEY == "change-me-before-production"
        assert settings.ALGORITHM == "HS256"

    def test_jwt_secret_property(self):
        """JWT_SECRET property should return SECRET_KEY."""
        settings = SecuritySettings()
        assert settings.JWT_SECRET == settings.SECRET_KEY

    def test_jwt_algorithm_property(self):
        """JWT_ALGORITHM property should return ALGORITHM."""
        settings = SecuritySettings()
        assert settings.JWT_ALGORITHM == settings.ALGORITHM


# =============================================================================
# Tests for NotificationSettings
# =============================================================================


class TestNotificationSettings:
    """Tests for NotificationSettings."""

    def test_notification_settings_defaults(self):
        """NotificationSettings should have correct defaults for port and flags."""
        settings = NotificationSettings()
        assert settings.MAIL_PORT == 587
        assert settings.MAIL_STARTTLS is True
        assert settings.MAIL_SSL_TLS is False
        assert settings.USE_CREDENTIALS is True
        assert settings.VALIDATE_CERTS is True


# =============================================================================
# Tests for S3Settings
# =============================================================================


class TestS3Settings:
    """Tests for S3Settings."""

    def test_s3_settings_defaults(self):
        """S3Settings should have correct defaults."""
        settings = S3Settings()
        assert settings.AWS_REGION == "us-east-1"
        assert settings.S3_BUCKET_NAME == "model-predictions"


# =============================================================================
# Tests for normalize_database_url
# =============================================================================


class TestNormalizeDatabaseUrl:
    """Tests for normalize_database_url utility."""

    def test_asyncpg_url_unchanged(self):
        """Already async URL should be returned as-is."""
        url = "postgresql+asyncpg://user:pass@host/db"
        assert normalize_database_url(url) == url

    def test_postgresql_url_converted(self):
        """postgresql:// URL should be converted to asyncpg."""
        url = "postgresql://user:pass@host/db"
        assert normalize_database_url(url) == url.replace(
            "postgresql://", "postgresql+asyncpg://"
        )

    def test_postgres_url_converted(self):
        """postgres:// URL should be converted to asyncpg."""
        url = "postgres://user:pass@host/db"
        assert normalize_database_url(url) == "postgresql+asyncpg://user:pass@host/db"

    def test_unknown_url_unchanged(self):
        """Non-PostgreSQL URLs should be returned as-is."""
        url = "mysql://user:pass@host/db"
        assert normalize_database_url(url) == url

    def test_whitespace_stripped(self):
        """Leading/trailing whitespace should be stripped."""
        url = "  postgresql+asyncpg://user:pass@host/db  "
        assert normalize_database_url(url) == url.strip()


# =============================================================================
# Tests for to_sync_database_url
# =============================================================================


class TestToSyncDatabaseUrl:
    """Tests for to_sync_database_url utility."""

    def test_async_to_sync_conversion(self):
        """Should replace asyncpg driver with sync driver."""
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        assert to_sync_database_url(url) == "postgresql://user:pass@host:5432/db"

    def test_already_sync_url_unchanged(self):
        """Non-asyncpg URLs should be returned unchanged."""
        url = "postgresql://user:pass@host:5432/db"
        assert to_sync_database_url(url) == url


# =============================================================================
# Tests for module-level instances
# =============================================================================


class TestModuleInstances:
    """Tests for module-level configuration instances."""

    def test_app_settings_instance(self):
        """app_settings should be an instance of AppSettings."""
        assert isinstance(app_settings, AppSettings)

    def test_db_settings_instance(self):
        """db_settings should be an instance of DatabaseSettings."""
        assert isinstance(db_settings, DatabaseSettings)

    def test_security_settings_instance(self):
        """security_settings should be an instance of SecuritySettings."""
        assert isinstance(security_settings, SecuritySettings)

    def test_notification_settings_instance(self):
        """notification_settings should be an instance of NotificationSettings."""
        assert isinstance(notification_settings, NotificationSettings)

    def test_s3_settings_instance(self):
        """s3_settings should be an instance of S3Settings."""
        assert isinstance(s3_settings, S3Settings)
