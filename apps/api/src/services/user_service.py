from collections.abc import Mapping
from typing import Any
from uuid import UUID

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import app_settings
from src.core.errors import (
    BadCredentials,
    BadPassword,
    ClientNotVerified,
    EntityNotFound,
    InvalidToken,
)
from src.core.logger import get_logger
from src.database.postgres import User
from src.schemas.user_schemas import UserCreate
from src.utils.token_utils import (
    decode_url_safe_token,
    generate_access_token,
    generate_url_safe_token,
)
from src.worker.tasks import dispatch_email_with_template

from .base import BaseService

logger = get_logger(__name__)
MAX_BCRYPT_PASSWORD_BYTES = 72


class UserService(BaseService):
    """Handle user registration, email verification, and login."""

    def __init__(self, model: type[User], session: AsyncSession):
        super().__init__()
        self.model = model
        self.session = session

    async def _save_user(self, user: User) -> User:
        """Persist a user record and refresh it from the database."""

        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def _get_user_by_id_or_raise(self, user_id: UUID) -> User:
        """Return a user by ID or raise `EntityNotFound` if it does not exist."""

        user = await self.session.get(self.model, user_id)
        if user is None:
            raise EntityNotFound()
        return user

    @staticmethod
    def _hash_password(password: str | None) -> str:
        """Hash a plain-text password and normalize password validation errors."""

        if password is None:
            raise BadPassword()

        try:
            password_bytes = password.encode("utf-8")
            if len(password_bytes) > MAX_BCRYPT_PASSWORD_BYTES:
                raise BadPassword()

            return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")
        except ValueError as exc:
            logger.error("Error hashing password for new user", exc_info=True)
            raise BadPassword() from exc

    @staticmethod
    def _build_verification_url(token: str, router_prefix: str) -> str:
        """Build the email verification link sent to newly registered users."""

        return f"{app_settings.APP_HTTP_PROTOCOL}://{app_settings.APP_DOMAIN}/{router_prefix}/verify?token={token}"

    async def _send_verification_email(self, user: User, router_prefix: str) -> None:
        """Queue the account verification email for a newly created user."""

        token = generate_url_safe_token({"id": str(user.id)})
        await dispatch_email_with_template(
            recipients=[user.email],
            subject="Verify Your Account With PyTorch Model",
            context={
                "username": user.email,
                "verification_url": self._build_verification_url(token, router_prefix),
            },
            template_name="mail_email_verify.html",
        )

    async def _create_pending_user_and_send_verification_email(
        self,
        user_data: Mapping[str, Any],
        router_prefix: str,
    ) -> User:
        """Create an unverified user account and email the verification link."""

        user_payload = dict(user_data)
        password = user_payload.pop("password", None)
        password_hash = self._hash_password(password)

        user = self.model(**user_payload, password_hash=password_hash)
        saved_user = await self._save_user(user)
        await self._send_verification_email(saved_user, router_prefix)
        return saved_user

    async def register_user(self, user: UserCreate) -> User:
        """
        Create a new user account and send the email verification message.

        The user is returned immediately, but they cannot log in until their
        email address has been verified.
        """

        return await self._create_pending_user_and_send_verification_email(
            user_data=user.model_dump(),
            router_prefix="user",
        )

    async def verify_user_email(self, token: str) -> None:
        """Mark a user's email address as verified using the emailed token."""

        token_data = decode_url_safe_token(token)
        if not token_data:
            raise InvalidToken()

        try:
            user_id = UUID(token_data["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidToken() from exc

        user = await self._get_user_by_id_or_raise(user_id)
        user.email_verified = True
        await self._save_user(user)

    async def _get_user_by_email(self, email: str) -> User | None:
        """Look up a user by email address."""

        return await self.session.scalar(select(self.model).where(self.model.email == email))

    async def _authenticate_user(self, email: str, password: str) -> User:
        """Return the authenticated user or raise `BadCredentials`."""

        user = await self._get_user_by_email(email)
        if user is None:
            raise BadCredentials()

        try:
            password_matches = bcrypt.checkpw(
                password.encode("utf-8"),
                user.password_hash.encode("utf-8"),
            )
        except ValueError:
            raise BadCredentials() from None

        if not password_matches:
            raise BadCredentials()

        return user

    async def authenticate_user_and_create_token(
        self,
        email: str,
        password: str,
    ) -> str:
        """
        Authenticate a user and return a JWT access token.

        Raises:
            BadCredentials: If the email does not exist or the password is wrong.
            ClientNotVerified: If the user has not verified their email yet.
        """

        user = await self._authenticate_user(email, password)
        if not user.email_verified:
            raise ClientNotVerified()

        return generate_access_token(
            data={
                "user": {
                    "id": str(user.id),
                },
            }
        )
