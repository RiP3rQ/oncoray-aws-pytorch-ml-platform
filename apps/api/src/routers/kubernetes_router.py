from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.session import get_session, ping_database

router = APIRouter(include_in_schema=False)

_session = Depends(get_session)


def _probe_response(
    *,
    db_ready: bool | None = None,
) -> dict[str, object]:
    """
    Build a consistent payload for Kubernetes probes.
    """
    checks = {
        "database": db_ready,
    }
    payload: dict[str, object] = {
        "service": "core-api",
        "status": "ok",
    }
    if any(value is not None for value in checks.values()):
        filtered_checks = {name: value for name, value in checks.items() if value is not None}
        payload["checks"] = filtered_checks
        payload["status"] = "ok" if all(filtered_checks.values()) else "degraded"
    return payload


async def _dependency_probe(session: AsyncSession) -> JSONResponse | dict[str, object]:
    """
    Run shared dependency checks used by readiness, startup, and health probes.
    """
    db_ready = await ping_database(session)
    payload = _probe_response(db_ready=db_ready)
    if not db_ready:
        return JSONResponse(status_code=503, content=payload)
    return payload


@router.get("/livez")
async def get_livez() -> dict[str, object]:
    """
    Kubernetes liveness probe.
    """
    return _probe_response()


@router.get("/readyz", response_model=None)
async def get_readyz(
    session: AsyncSession = _session,
) -> dict[str, object] | JSONResponse:
    """
    Kubernetes readiness probe.
    """
    return await _dependency_probe(session)


@router.get("/startupz", response_model=None)
async def get_startupz(
    session: AsyncSession = _session,
) -> dict[str, object] | JSONResponse:
    """
    Kubernetes startup probe.
    """
    return await _dependency_probe(session)


@router.get("/health", response_model=None)
async def get_health(
    session: AsyncSession = _session,
) -> dict[str, object] | JSONResponse:
    """
    Compatibility health probe that mirrors readiness.
    """
    return await _dependency_probe(session)


@router.get("/healthz", response_model=None)
async def get_healthz(
    session: AsyncSession = _session,
) -> dict[str, object] | JSONResponse:
    """
    Compatibility health probe for common Kubernetes conventions.
    """
    return await _dependency_probe(session)
