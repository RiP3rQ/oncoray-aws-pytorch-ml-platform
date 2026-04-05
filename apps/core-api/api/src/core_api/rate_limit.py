from __future__ import annotations

import asyncio
from collections import defaultdict, deque
import time

from fastapi import HTTPException, Request, status

from core_api.config import get_settings


class MemoryRateLimiter:
    """Simple in-memory limiter for single-process auth protection."""

    def __init__(self, *, max_requests: int, window_seconds: int) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._events: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> None:
        now = time.monotonic()
        async with self._lock:
            events = self._events[key]
            cutoff = now - self._window_seconds
            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= self._max_requests:
                retry_after = max(1, int(self._window_seconds - (now - events[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many authentication attempts. Please try again later.",
                    headers={"Retry-After": str(retry_after)},
                )

            events.append(now)

    async def reset(self) -> None:
        async with self._lock:
            self._events.clear()


settings = get_settings()
auth_rate_limiter = MemoryRateLimiter(
    max_requests=settings.auth_rate_limit_max_requests,
    window_seconds=settings.auth_rate_limit_window_seconds,
)


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()

    if request.client is not None:
        return request.client.host

    return "unknown"


async def enforce_auth_rate_limit(request: Request, *, action: str, identifier: str) -> None:
    normalized_identifier = identifier.strip().lower()
    key = f"{action}:{get_client_ip(request)}:{normalized_identifier}"
    await auth_rate_limiter.check(key)
