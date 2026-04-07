"""
Pytest fixtures and configuration for FastAPI testing.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import get_user_service, get_model_service
from src.core.security import oauth2_scheme_user
from src.database.postgres import User as UserModel
from src.database.session import get_session


# =============================================================================
# Fake Models
# =============================================================================


def create_fake_user(
        email: str = "test@example.com",
        email_verified: bool = False,
) -> MagicMock:
    """Create a fake User model instance."""
    user = MagicMock(spec=UserModel)
    user.id = uuid4()
    user.email = email
    user.email_verified = email_verified
    user.password_hash = "$2b$12$fake_hash_for_testing"
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


def create_fake_model(
        name: str = "TestModel",
        description: str = "A test model",
        version: str = "v1",
) -> MagicMock:
    """Create a fake LLMModel instance."""
    model = MagicMock()
    model.id = uuid4()
    model.name = name
    model.description = description
    model.version = version
    model.created_at = datetime.now(timezone.utc)
    model.updated_at = datetime.now(timezone.utc)
    return model


# =============================================================================
# Mock Services
# =============================================================================


class MockUserService:
    """Mock UserService for testing."""

    def __init__(self, user: MagicMock | None = None):
        self._user = user or create_fake_user()

    async def register_user(self, user_data):
        return self._user

    async def authenticate_user_and_create_token(
            self, email: str, password: str
    ) -> str:
        if email == "valid@example.com" and password == "validpassword":
            return "fake.jwt.token"
        from src.core.errors import BadCredentials

        raise BadCredentials()

    async def verify_user_email(self, token: str) -> None:
        pass


class MockModelService:
    """Mock ModelService for testing."""

    def __init__(self, models: list[MagicMock] | None = None):
        self._models = models or [create_fake_model()]

    async def get_all(self) -> list:
        return self._models

    async def get(self, model_id) -> MagicMock:
        for m in self._models:
            if str(m.id) == str(model_id):
                return m
        from src.core.errors import EntityNotFound

        raise EntityNotFound(f"Model '{model_id}' was not found.")

    async def predict_with_image(
            self, model_id, image_data: bytes, filename: str
    ) -> dict:
        from uuid import UUID

        return {
            "model_id": UUID(str(model_id)),
            "prediction": "cat",
            "confidence": 0.95,
            "image_s3_key": f"predictions/{uuid4()}.jpg",
        }


class MockS3Service:
    """Mock S3Service for testing."""

    async def upload_image(self, data: bytes, filename: str) -> str:
        return f"predictions/{uuid4()}.jpg"


# =============================================================================
# Mock Database Session
# =============================================================================


class MockAsyncSession:
    """Mock AsyncSession for testing."""

    def __init__(
            self, user: MagicMock | None = None, models: list[MagicMock] | None = None
    ):
        self._user = user or create_fake_user(email_verified=True)
        self._models = models or [
            create_fake_model(),
            create_fake_model(name="SecondModel"),
        ]

    async def get(self, model, id):

        if model.__name__ == "User":
            return self._user
        elif model.__name__ == "LLMModel":
            for m in self._models:
                if str(m.id) == str(id):
                    return m
            return None
        return None

    async def execute(self, query):
        """Mock execute - returns a result with scalars().all()"""
        result = MagicMock()
        if "LLMModel" in str(query):
            result.scalars.return_value.all.return_value = self._models
        else:
            result.scalars.return_value.all.return_value = []
        return result

    def add(self, obj):
        pass

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass

    async def scalar(self, query):
        return self._user


# =============================================================================
# Mock Redis
# =============================================================================


async def mock_add_jti_to_blacklist(jti: str) -> None:
    """Mock add_jti_to_blacklist."""
    pass


async def mock_is_jti_blacklisted(jti: str) -> bool:
    """Mock is_jti_blacklisted."""
    return False


async def mock_ping_redis() -> bool:
    """Mock ping_redis."""
    return True


async def mock_ping_database(session) -> bool:
    """Mock ping_database."""
    return True


# =============================================================================
# Fixture Factory
# =============================================================================


@pytest.fixture
def mock_session() -> MockAsyncSession:
    """Create a mock database session."""
    return MockAsyncSession()


@pytest.fixture
def mock_user() -> MagicMock:
    """Create a mock user."""
    return create_fake_user(email_verified=True)


@pytest.fixture
def mock_models() -> list[MagicMock]:
    """Create mock models."""
    return [create_fake_model(), create_fake_model(name="SecondModel")]


@pytest.fixture
def mock_user_service(mock_user: MagicMock) -> MockUserService:
    """Create a mock user service."""
    return MockUserService(user=mock_user)


@pytest.fixture
def mock_model_service(mock_models: list[MagicMock]) -> MockModelService:
    """Create a mock model service."""
    return MockModelService(models=mock_models)


# =============================================================================
# App Fixture with Overridden Dependencies
# =============================================================================


@pytest.fixture
def app(
        mock_session: MockAsyncSession,
        mock_user_service: MockUserService,
        mock_model_service: MockModelService,
) -> FastAPI:
    """
    Create a FastAPI test app with mocked dependencies.
    """
    # Import here to avoid circular imports
    from main import app as main_app

    # Override session dependency
    async def override_get_session():
        yield mock_session

    # Override user service dependency
    async def override_get_user_service(session: AsyncSession):
        return mock_user_service

    # Override model service dependency
    async def override_get_model_service(session: AsyncSession):
        return mock_model_service

    # Apply patches for redis and database ping functions
    with (
        patch("src.database.redis.add_jti_to_blacklist", mock_add_jti_to_blacklist),
        patch("src.database.redis.is_jti_blacklisted", mock_is_jti_blacklisted),
        patch("src.database.redis.ping_redis", mock_ping_redis),
        patch("src.database.session.ping_database", mock_ping_database),
    ):
        # Override FastAPI dependencies
        main_app.dependency_overrides[get_session] = override_get_session
        main_app.dependency_overrides[get_user_service] = override_get_user_service
        main_app.dependency_overrides[get_model_service] = override_get_model_service

        yield main_app

        main_app.dependency_overrides.clear()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create a test client."""
    return TestClient(app)


# =============================================================================
# Authenticated Client Fixture
# =============================================================================


@pytest.fixture
def authenticated_client(app: FastAPI, mock_user: MagicMock) -> TestClient:
    """
    Create an authenticated test client with a valid mock user.
    """
    from src.utils.token_utils import generate_access_token

    # Generate a mock token for the authenticated user
    token = generate_access_token(data={"user": {"id": str(mock_user.id)}})

    # Override oauth2 scheme to return our mock token
    async def override_oauth2_scheme():
        return token

    app.dependency_overrides[oauth2_scheme_user] = override_oauth2_scheme

    client = TestClient(app)
    yield client

    app.dependency_overrides.pop(oauth2_scheme_user, None)
