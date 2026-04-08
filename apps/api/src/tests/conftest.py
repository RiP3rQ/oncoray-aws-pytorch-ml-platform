"""
Pytest fixtures and configuration for FastAPI testing.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

# Add project root to Python path so 'src' can be imported
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# Fake Models
# =============================================================================


def create_fake_user(
        email: str = "test@example.com",
        email_verified: bool = False,
) -> MagicMock:
    """Create a fake User model instance."""
    user = MagicMock()
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
# Fixtures
# =============================================================================


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    return MockAsyncSession()


@pytest.fixture
def mock_user():
    """Create a mock user."""
    return create_fake_user(email_verified=True)


@pytest.fixture
def mock_models():
    """Create mock models."""
    return [create_fake_model(), create_fake_model(name="SecondModel")]


@pytest.fixture
def mock_user_service(mock_user):
    """Create a mock user service."""
    return MockUserService(user=mock_user)


@pytest.fixture
def mock_model_service(mock_models):
    """Create a mock model service."""
    return MockModelService(models=mock_models)


# =============================================================================
# App Fixture
# =============================================================================


@pytest.fixture
def app(mock_session, mock_user_service, mock_model_service):
    """Create a FastAPI test app with mocked dependencies."""
    from src.core.dependencies import get_user_service, get_model_service
    from src.database.session import get_session
    from main import app as main_app

    # Override FastAPI dependencies (bypass real DB/service wiring)
    async def override_get_session():
        yield mock_session

    main_app.dependency_overrides[get_session] = override_get_session
    main_app.dependency_overrides[get_user_service] = lambda: mock_user_service
    main_app.dependency_overrides[get_model_service] = lambda: mock_model_service

    # Patch real I/O calls that would hang without running services.
    # Must patch at the import location (where the name is used), not the
    # definition location, because Python binds imports to local names.
    patches = [
        patch(
            "src.routers.kubernetes_router.ping_redis", new=AsyncMock(return_value=True)
        ),
        patch(
            "src.routers.kubernetes_router.ping_database",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "src.core.dependencies.is_jti_blacklisted",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "src.routers.user_router.add_jti_to_blacklist",
            new=AsyncMock(return_value=None),
        ),
    ]

    for p in patches:
        p.start()

    yield main_app

    main_app.dependency_overrides.clear()
    for p in patches:
        p.stop()


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def authenticated_client(app, mock_user):
    """Create an authenticated test client."""
    from src.utils.token_utils import generate_access_token
    from src.core.security import oauth2_scheme_user

    token = generate_access_token(data={"user": {"id": str(mock_user.id)}})

    async def override_oauth2_scheme():
        return token

    app.dependency_overrides[oauth2_scheme_user] = override_oauth2_scheme
    client = TestClient(app)
    yield client
    app.dependency_overrides.pop(oauth2_scheme_user, None)
