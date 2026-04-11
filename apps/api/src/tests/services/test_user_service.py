"""
Tests for UserService - user registration, authentication, email verification.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.errors import (
    BadCredentials,
    BadPassword,
    ClientNotVerified,
    EntityNotFound,
    InvalidToken,
)
from src.database.postgres import User
from src.services.user_service import UserService

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession for unit tests."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.get = AsyncMock()
    session.scalar = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def fake_user():
    """Create a fake User instance for testing."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.email = "test@example.com"
    user.password_hash = "$2b$12$fake_hash_for_testing"
    user.email_verified = True
    user.created_at = datetime.now(UTC)
    user.updated_at = datetime.now(UTC)
    return user


@pytest.fixture
def user_service(mock_session):
    """Create a UserService instance with mocked session."""
    return UserService(model=User, session=mock_session)


# =============================================================================
# Tests for _hash_password
# =============================================================================


class TestHashPassword:
    """Tests for UserService._hash_password static method."""

    def test_hash_password_returns_hash(self):
        """_hash_password should return a bcrypt hash string."""
        result = UserService._hash_password("securepassword123")
        assert isinstance(result, str)
        assert result.startswith("$2b$")

    def test_hash_password_different_hashes_for_same_password(self):
        """_hash_password should generate different hashes (different salts)."""
        hash1 = UserService._hash_password("samepassword")
        hash2 = UserService._hash_password("samepassword")
        assert hash1 != hash2  # Different salts

    def test_hash_password_none_raises_bad_password(self):
        """_hash_password should raise BadPassword when password is None."""
        with pytest.raises(BadPassword):
            UserService._hash_password(None)

    def test_hash_password_too_long_raises_bad_password(self):
        """_hash_password should raise BadPassword for passwords > 72 bytes."""
        long_password = "x" * 73  # bcrypt max is 72 bytes
        with pytest.raises(BadPassword):
            UserService._hash_password(long_password)

    def test_hash_password_at_boundary_72_bytes(self):
        """_hash_password should accept passwords exactly 72 bytes long."""
        password_72_bytes = "x" * 72
        result = UserService._hash_password(password_72_bytes)
        assert isinstance(result, str)


# =============================================================================
# Tests for _save_user
# =============================================================================


class TestSaveUser:
    """Tests for UserService._save_user."""

    @pytest.mark.asyncio
    async def test_save_user_calls_add_commit_refresh(
            self, user_service, mock_session, fake_user
    ):
        """_save_user should add, commit, and refresh the user."""
        await user_service._save_user(fake_user)

        mock_session.add.assert_called_once_with(fake_user)
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once_with(fake_user)

    @pytest.mark.asyncio
    async def test_save_user_returns_user(self, user_service, mock_session, fake_user):
        """_save_user should return the saved user."""
        result = await user_service._save_user(fake_user)
        assert result == fake_user


# =============================================================================
# Tests for _get_user_by_id_or_raise
# =============================================================================


class TestGetUserByIdOrRaise:
    """Tests for UserService._get_user_by_id_or_raise."""

    @pytest.mark.asyncio
    async def test_get_user_by_id_returns_user(
            self, user_service, mock_session, fake_user
    ):
        """_get_user_by_id_or_raise should return user when found."""
        user_id = uuid4()
        mock_session.get.return_value = fake_user

        result = await user_service._get_user_by_id_or_raise(user_id)

        mock_session.get.assert_called_once_with(User, user_id)
        assert result == fake_user

    @pytest.mark.asyncio


async def test_get_user_by_id_raises_when_not_found(
            self, user_service, mock_session
    ):
    """_get_user_by_id_or_raise should raise EntityNotFound if not found."""
        mock_session.get.return_value = None

        with pytest.raises(EntityNotFound):
            await user_service._get_user_by_id_or_raise(uuid4())


# =============================================================================
# Tests for _build_verification_url
# =============================================================================


class TestBuildVerificationUrl:
    """Tests for UserService._build_verification_url."""

    def test_build_verification_url(self):
        """_build_verification_url should construct the correct verification URL."""
        url = UserService._build_verification_url("some_token", "user")
        assert "http://" in url
        assert "/user/verify?token=some_token" in url


# =============================================================================
# Tests for _send_verification_email
# =============================================================================


class TestSendVerificationEmail:
    """Tests for UserService._send_verification_email."""

    @pytest.mark.asyncio
    async def test_send_verification_email_calls_task(
            self, user_service, mock_session, fake_user
    ):
        """_send_verification_email should queue the email verification task."""
        with patch(
                "src.services.user_service.send_email_with_template_async",
                new_callable=AsyncMock,
        ) as mock_send:
            await user_service._send_verification_email(fake_user, "user")

            mock_send.assert_called_once()
            call_kwargs = mock_send.call_args[1]
            assert call_kwargs["recipients"] == [fake_user.email]
            assert call_kwargs["template_name"] == "mail_email_verify.html"


# =============================================================================
# Tests for _create_pending_user_and_send_verification_email
# =============================================================================


class TestCreatePendingUserAndSendVerificationEmail:
    """Tests for UserService._create_pending_user_and_send_verification_email."""

    @pytest.mark.asyncio
    async def test_create_pending_user_hashes_password(
            self, user_service, mock_session, fake_user
    ):
        """_create_pending_user_and_send_verification_email should hash the password."""
        mock_session.refresh.side_effect = lambda obj: None

        with patch(
                "src.services.user_service.send_email_with_template_async",
                new_callable=AsyncMock,
        ):
            user_data = {"email": "new@example.com", "password": "securepassword123"}

            with patch.object(
                    user_service,
                    "_save_user",
                    new_callable=AsyncMock,
                    return_value=fake_user,
            ):
                await user_service._create_pending_user_and_send_verification_email(
                        user_data, "user"
                    )

    @pytest.mark.asyncio


async def test_create_pending_user_raises_bad_password_when_none(
            self, user_service, mock_session
    ):
    """_create_pending_user_and_send_verification_email raises BadPassword when password is None."""
        user_data = {"email": "new@example.com"}

        with pytest.raises(BadPassword):
            await user_service._create_pending_user_and_send_verification_email(
                user_data, "user"
            )


# =============================================================================
# Tests for register_user
# =============================================================================


class TestRegisterUser:
    """Tests for UserService.register_user."""

    @pytest.mark.asyncio
    async def test_register_user_creates_user(
            self, user_service, mock_session, fake_user
    ):
        """register_user should create and return a new user."""
        user_create = MagicMock()
        user_create.model_dump.return_value = {
            "email": "new@example.com",
            "password": "securepassword123",
        }

        with patch.object(
                user_service,
                "_create_pending_user_and_send_verification_email",
                new_callable=AsyncMock,
                return_value=fake_user,
        ) as mock_create:
            result = await user_service.register_user(user_create)

            mock_create.assert_called_once_with(
                user_data={"email": "new@example.com", "password": "securepassword123"},
                router_prefix="user",
            )
            assert result == fake_user


# =============================================================================
# Tests for verify_user_email
# =============================================================================


class TestVerifyUserEmail:
    """Tests for UserService.verify_user_email."""

    @pytest.mark.asyncio
    async def test_verify_user_email_success(
            self, user_service, mock_session, fake_user
    ):
        """verify_user_email should verify email when token is valid."""
        user_id = str(fake_user.id)

        with (
            patch(
                "src.services.user_service.decode_url_safe_token",
                return_value={"id": user_id},
            ),
            patch.object(
                user_service, "_save_user", new_callable=AsyncMock
            ) as mock_save,
        ):
            mock_session.get.return_value = fake_user

            await user_service.verify_user_email("valid_token")

            assert fake_user.email_verified is True
            mock_save.assert_called_once_with(fake_user)

    @pytest.mark.asyncio
    async def test_verify_user_email_invalid_token(self, user_service, mock_session):
        """verify_user_email should raise InvalidToken for invalid/empty token."""
        with (
            patch("src.services.user_service.decode_url_safe_token", return_value=None),
            pytest.raises(InvalidToken),
        ):
            await user_service.verify_user_email("invalid_token")

    @pytest.mark.asyncio
    async def test_verify_user_email_missing_id_key(self, user_service, mock_session):
        """verify_user_email should raise InvalidToken when token data lacks 'id'."""
        with (
            patch(
                "src.services.user_service.decode_url_safe_token",
                return_value={"wrong_key": "value"},
            ),
            pytest.raises(InvalidToken),
        ):
            await user_service.verify_user_email("token_no_id")

    @pytest.mark.asyncio
    async def test_verify_user_email_invalid_uuid(self, user_service, mock_session):
        """verify_user_email should raise InvalidToken when id is not a valid UUID."""
        with (
            patch(
                "src.services.user_service.decode_url_safe_token",
                return_value={"id": "not-a-uuid"},
            ),
            pytest.raises(InvalidToken),
        ):
            await user_service.verify_user_email("token_bad_uuid")

    @pytest.mark.asyncio
    async def test_verify_user_email_nonexistent_user(self, user_service, mock_session):
        """verify_user_email should raise EntityNotFound when user doesn't exist."""
        mock_session.get.return_value = None

        with (
            patch(
                "src.services.user_service.decode_url_safe_token",
                return_value={"id": str(uuid4())},
            ),
            pytest.raises(EntityNotFound),
        ):
            await user_service.verify_user_email("valid_token_nonexistent_user")


# =============================================================================
# Tests for _get_user_by_email
# =============================================================================


class TestGetUserByEmail:
    """Tests for UserService._get_user_by_email."""

    @pytest.mark.asyncio
    async def test_get_user_by_email_returns_user(
            self, user_service, mock_session, fake_user
    ):
        """_get_user_by_email should return the user when found."""
        mock_session.scalar.return_value = fake_user

        result = await user_service._get_user_by_email("test@example.com")

        assert result == fake_user

    @pytest.mark.asyncio
    async def test_get_user_by_email_returns_none(self, user_service, mock_session):
        """_get_user_by_email should return None when user not found."""
        mock_session.scalar.return_value = None

        result = await user_service._get_user_by_email("nonexistent@example.com")

        assert result is None


# =============================================================================
# Tests for _authenticate_user
# =============================================================================


class TestAuthenticateUser:
    """Tests for UserService._authenticate_user."""

    @pytest.mark.asyncio
    async def test_authenticate_user_success(
            self, user_service, mock_session, fake_user
    ):
        """_authenticate_user should return user with correct credentials."""
        mock_session.scalar.return_value = fake_user

        with patch("src.services.user_service.bcrypt.checkpw", return_value=True):
            result = await user_service._authenticate_user(
                "test@example.com", "validpassword"
            )

            assert result == fake_user

    @pytest.mark.asyncio
    async def test_authenticate_user_raises_bad_credentials_when_not_found(
            self, user_service, mock_session
    ):
        """_authenticate_user should raise BadCredentials when user not found."""
        mock_session.scalar.return_value = None

        with pytest.raises(BadCredentials):
            await user_service._authenticate_user("notfound@example.com", "password")

    @pytest.mark.asyncio
    async def test_authenticate_user_raises_bad_credentials_wrong_password(
            self, user_service, mock_session, fake_user
    ):
        """_authenticate_user should raise BadCredentials with wrong password."""
        mock_session.scalar.return_value = fake_user


with (
    patch("src.services.user_service.bcrypt.checkpw", return_value=False),
    pytest.raises(BadCredentials),
):
    await user_service._authenticate_user(
                    "test@example.com", "wrongpassword"
    )

    @pytest.mark.asyncio
    async def test_authenticate_user_raises_bad_credentials_on_bcrypt_error(
            self, user_service, mock_session, fake_user
    ):
        """_authenticate_user should raise BadCredentials when bcrypt raises ValueError."""
        mock_session.scalar.return_value = fake_user

        with (
            patch(
                "src.services.user_service.bcrypt.checkpw",
                side_effect=ValueError("bad hash"),
            ),
            pytest.raises(BadCredentials),
        ):
            await user_service._authenticate_user("test@example.com", "password")


# =============================================================================
# Tests for authenticate_user_and_create_token
# =============================================================================


class TestAuthenticateUserAndCreateToken:
    """Tests for UserService.authenticate_user_and_create_token."""

    @pytest.mark.asyncio


async def test_authenticate_and_create_token_success(
            self, user_service, mock_session, fake_user
    ):
    """authenticate_user_and_create_token should return a JWT for verified user."""
        mock_session.scalar.return_value = fake_user

        with (
            patch("src.services.user_service.bcrypt.checkpw", return_value=True),
            patch(
                "src.services.user_service.generate_access_token",
                return_value="fake.jwt.token",
            ),
        ):
            result = await user_service.authenticate_user_and_create_token(
                "test@example.com", "validpassword"
            )

            assert result == "fake.jwt.token"

    @pytest.mark.asyncio
    async def test_authenticate_and_create_token_raises_client_not_verified(
            self, user_service, mock_session, fake_user
    ):
        """authenticate_user_and_create_token should raise ClientNotVerified for unverified."""
        fake_user.email_verified = False
        mock_session.scalar.return_value = fake_user


with (
    patch("src.services.user_service.bcrypt.checkpw", return_value=True),
    pytest.raises(ClientNotVerified),
):
    await user_service.authenticate_user_and_create_token(
                    "test@example.com", "validpassword"
    )

    @pytest.mark.asyncio
    async def test_authenticate_and_create_token_raises_bad_credentials(
        self, user_service, mock_session
    ):
        """authenticate_user_and_create_token should raise BadCredentials with wrong email."""
        mock_session.scalar.return_value = None

        with pytest.raises(BadCredentials):
            await user_service.authenticate_user_and_create_token(
                "wrong@example.com", "password"
            )
