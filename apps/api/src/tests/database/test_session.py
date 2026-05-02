"""
Tests for database session management.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.session import get_session, ping_database

# =============================================================================
# Tests for get_session
# =============================================================================


class TestGetSession:
    """Tests for get_session async generator."""

    @pytest.mark.asyncio
    async def test_get_session_yields_session(self):
        """get_session should yield an AsyncSession."""
        with patch("src.database.session.async_sessionmaker") as mock_sessionmaker:
            mock_factory = MagicMock()
            # Make the context manager work
            mock_session_instance = AsyncMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_sessionmaker.return_value = mock_factory

            session_gen = get_session()
            session = await session_gen.__anext__()
            assert session is not None


# =============================================================================
# Tests for ping_database
# =============================================================================


class TestPingDatabase:
    """Tests for ping_database function."""

    @pytest.mark.asyncio
    async def test_ping_database_success(self):
        """ping_database should return True when database is reachable."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=None)

        result = await ping_database(mock_session)
        assert result is True
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_ping_database_failure(self):
        """ping_database should return False when database is unreachable."""
        from sqlalchemy.exc import SQLAlchemyError

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=SQLAlchemyError("Connection refused"))

        result = await ping_database(mock_session)
        assert result is False
