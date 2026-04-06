from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from scalar_fastapi import get_scalar_api_reference

from src.core.errors import FastApiCoreError
from src.routers.master_router import master_router

app = FastAPI()


@app.exception_handler(FastApiCoreError)
async def handle_core_error(_: Request, exc: FastApiCoreError) -> JSONResponse:
    """Translate domain exceptions into JSON HTTP responses."""
    return JSONResponse(status_code=exc.status, content={"detail": exc.detail})

# =============================== ROOT ENDPOINT ===============================

@app.get("/")
async def get_root():
    """
    Root endpoint for the API.
    """
    return {"service": "core-api", "status": "ok"}

# =============================== SCALAR DOCS ENDPOINT ===============================

@app.get("/scalar", include_in_schema=False)
async def get_scalar_docs():
    """
    Adds an Scalar API reference to the API, so we can use it in the Scalar console.
    """
    return get_scalar_api_reference(
        openapi_url="/openapi.json",
        title="Core API",
    )

# =============================== KUBERNETES READINESS ENDPOINT ===============================

@app.get("/livez")
async def get_livez():
    """
    Kubernetes readiness endpoint.
    """
    return {"status": "ok"}

# =============================== KUBERNETES LIVENESS ENDPOINT ===============================

@app.get("/readyz")
async def get_readyz():
    """
    Kubernetes liveness endpoint.
    """
    return {"status": "ok"}

# =============================== KUBERNETES HEALTH ENDPOINT ===============================

@app.get("/health")
async def get_health():
    """
    Kubernetes health endpoint.
    """
    return {"status": "ok"}

# =============================== MAIN ===============================
# Add all endpoints
app.include_router(master_router)
