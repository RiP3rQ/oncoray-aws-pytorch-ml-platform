"""
Tests for Redis operations - blacklist and ping.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# Tests for add_jti_to_blacklist
# =============================================================================


class TestAddJtiToBlacklist:
    """Tests for add_jti_to_blacklist."""

    @pytest.mark.asyncio
    async def test_add_jti_to_blacklist(self):
        """add_jti_to_blacklist should call redis_instance.set with jti."""
        with patch("src.database.redis.redis_instance") as mock_redis:
            mock_redis.set = AsyncMock(return_value=True)
            from src.database.redis import add_jti_to_blacklist

            await add_jti_to_blacklist("test_jti_123")

            mock_redis.set.assert_called_once_with("test_jti_123", "blacklisted")


# =============================================================================
# Tests for is_jti_blacklisted
# =============================================================================


class TestIsJtiBlacklisted:
    """Tests for is_jti_blacklisted."""

    @pytest.mark.asyncio
    async def test_jti_is_blacklisted(self):
        """is_jti_blacklisted should return truthy value when JTI exists in Redis."""
        with patch("src.database.redis.redis_instance") as mock_redis:
            mock_redis.exists = AsyncMock(return_value=1)
            from src.database.redis import is_jti_blacklisted

            result = await is_jti_blacklisted("blacklisted_jti")

            assert result  # Truthy check (1 is truthy)
            mock_redis.exists.assert_called_once_with("blacklisted_jti")

    @pytest.mark.asyncio
    async def test_jti_not_blacklisted(self):
        """is_jti_blacklisted should return falsy value when JTI doesn't exist in Redis."""
        with patch("src.database.redis.redis_instance") as mock_redis:
            mock_redis.exists = AsyncMock(return_value=0)
            from src.database.redis import is_jti_blacklisted

            result = await is_jti_blacklisted("not_blacklisted_jti")

            assert not result  # Falsy check (0 is falsy)


# =============================================================================
# Tests for ping_redis
# =============================================================================


class TestPingRedis:
    """Tests for ping_redis."""

    @pytest.mark.asyncio
    async def test_ping_redis_success(self):
        """ping_redis should return True when Redis is reachable."""
        with patch("src.database.redis.redis_instance") as mock_redis:
            mock_redis.ping = AsyncMock(return_value=True)
            from src.database.redis import ping_redis

            result = await ping_redis()

            assert result is True

    @pytest.mark.asyncio
    async def test_ping_redis_failure(self):
        """ping_redis should return False when Redis is unreachable."""
        from redis.exceptions import RedisError

        with patch("src.database.redis.redis_instance") as mock_redis:
            mock_redis.ping = AsyncMock(side_effect=RedisError("Connection refused"))
            from src.database.redis import ping_redis

            result = await ping_redis()

            assert result is False
