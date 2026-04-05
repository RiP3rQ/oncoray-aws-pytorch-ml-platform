from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core_api.auth import TokenValidationError, decode_access_token, hash_session_identifier
from core_api.db import get_db_session
from core_api.models import SessionToken


bearer_scheme = HTTPBearer(auto_error=False, bearerFormat="JWT", description="Signed JWT bearer access token.")
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_session(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DbSession,
) -> SessionToken:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = decode_access_token(credentials.credentials)
    except TokenValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    session_token = await db.scalar(
        select(SessionToken)
        .options(selectinload(SessionToken.user))
        .where(
            SessionToken.jti_hash == hash_session_identifier(claims.jti),
            SessionToken.user_id == claims.subject,
            SessionToken.expires_at >= claims.expires_at,
        ),
    )
    if session_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return session_token
