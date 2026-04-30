"""
Tests for core dependency injection functions.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.errors import ClientNotAuthorized, InvalidToken

# =============================================================================
# Tests for _get_access_token
# =============================================================================


class TestGetAccessToken:
    """Tests for _get_access_token dependency function."""

    @pytest.mark.asyncio
    async def test_valid_token_returns_data(self):
        """_get_access_token should return decoded data for valid token."""
        from src.core.dependencies import _get_access_token

        user_id = str(uuid4())
        token_data = {
            "user": {"id": user_id},
            "jti": str(uuid4()),
            "exp": 9999999999,
        }

        with (
            patch(
                "src.core.dependencies.decode_access_token",
                return_value=token_data,
            ),
            patch(
                "src.core.dependencies.is_jti_blacklisted",
                new=AsyncMock(return_value=False),
            ),
        ):
            result = await _get_access_token("valid_token")
            assert result == token_data

    @pytest.mark.asyncio
    async def test_invalid_token_raises_error(self):
        """_get_access_token should raise InvalidToken for invalid token."""
        from src.core.dependencies import _get_access_token

        with (
            patch(
                "src.core.dependencies.decode_access_token",
                return_value=None,
            ),
            pytest.raises(InvalidToken),
        ):
            await _get_access_token("invalid_token")

    @pytest.mark.asyncio
    async def test_blacklisted_token_raises_error(self):
        """_get_access_token should raise InvalidToken for blacklisted JTI."""
        from src.core.dependencies import _get_access_token

        token_data = {
            "user": {"id": str(uuid4())},
            "jti": str(uuid4()),
        }

        with (
            patch(
                "src.core.dependencies.decode_access_token",
                return_value=token_data,
            ),
            patch(
                "src.core.dependencies.is_jti_blacklisted",
                new=AsyncMock(return_value=True),
            ),
            pytest.raises(InvalidToken),
        ):
            await _get_access_token("blacklisted_token")


# =============================================================================
# Tests for get_current_user
# =============================================================================


class TestGetCurrentUser:
    """Tests for get_current_user dependency function."""

    @pytest.mark.asyncio
    async def test_get_current_user_found(self):
        """get_current_user should return user when found in DB."""
        from src.core.dependencies import get_current_user

        user_id = uuid4()
        token_data = {"user": {"id": str(user_id)}}
        mock_user = MagicMock()
        mock_user.id = user_id

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_user

        result = await get_current_user(token_data=token_data, session=mock_session)
        assert result == mock_user

    @pytest.mark.asyncio
    async def test_get_current_user_not_found_raises(self):
        """get_current_user should raise ClientNotAuthorized when user not found."""
        from src.core.dependencies import get_current_user

        token_data = {"user": {"id": str(uuid4())}}
        mock_session = AsyncMock()
        mock_session.get.return_value = None

        with pytest.raises(ClientNotAuthorized):
            await get_current_user(token_data=token_data, session=mock_session)


# =============================================================================
# Tests for service dependency providers
# =============================================================================


class TestServiceDependencies:
    """Tests for service dependency provider functions."""

    def test_get_user_service(self):
        """get_user_service should return a UserService instance."""
        from src.core.dependencies import get_user_service
        from src.services.user_service import UserService

        mock_session = MagicMock()
        service = get_user_service(session=mock_session)
        assert isinstance(service, UserService)

    def test_get_model_catalog(self):
        """get_model_catalog should return a ModelCatalog instance."""
        from src.core.dependencies import get_model_catalog
        from src.services.model_catalog import ModelCatalog

        mock_session = MagicMock()
        catalog = get_model_catalog(session=mock_session)
        assert isinstance(catalog, ModelCatalog)

    def test_get_s3_service(self):
        """get_s3_service should return an S3Service instance."""
        from src.core.dependencies import get_s3_service
        from src.services.s3_service import S3Service

        service = get_s3_service()
        assert isinstance(service, S3Service)

    def test_get_model_runtime_clients_returns_empty_map_without_urls(self):
        """get_model_runtime_clients should return empty map when URLs are unset."""
        from src.core.dependencies import get_model_runtime_clients

        with patch("src.core.dependencies.model_service_settings") as mock_settings:
            mock_settings.model_service_urls = {}
            result = get_model_runtime_clients()

        assert result == {}

    def test_get_model_runtime_clients_builds_clients_when_urls_set(self):
        """get_model_runtime_clients should build clients when URLs exist."""
        from src.core.dependencies import get_model_runtime_clients
        from src.services.model_runtime_client import ModelRuntimeClient

        with patch("src.core.dependencies.model_service_settings") as mock_settings:
            mock_settings.model_service_urls = {
                "effnetb0": "http://effnet-service:8000",
                "vitb16": "http://vit-service:8000",
            }
            mock_settings.MODEL_SERVICE_TIMEOUT_SECONDS = 12.5
            result = get_model_runtime_clients()

        assert isinstance(result["effnetb0"], ModelRuntimeClient)
        assert isinstance(result["vitb16"], ModelRuntimeClient)
        assert result["effnetb0"].base_url == "http://effnet-service:8000"
        assert result["vitb16"].base_url == "http://vit-service:8000"
        assert result["effnetb0"].timeout_seconds == 12.5

    def test_get_model_runtime_pool(self):
        """get_model_runtime_pool should return a ModelRuntimePool instance."""
        from src.core.dependencies import get_model_runtime_pool
        from src.services.model_runtime_pool import ModelRuntimePool

        service = get_model_runtime_pool(model_runtime_clients={})
        assert isinstance(service, ModelRuntimePool)
