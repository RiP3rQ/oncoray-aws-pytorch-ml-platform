from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from scalar_fastapi import get_scalar_api_reference

from src.api_types.enums import APITag
from src.core.config import app_settings, validate_production_settings
from src.core.errors import add_exception_handlers
from src.core.logger import configure_logging, get_logger
from src.core.observability import configure_observability
from src.routers.master_router import master_router

# =============================== LOGGER ===============================
validate_production_settings()
configure_logging()
logger = get_logger(__name__)

# =============================== FASTAPI APP ===============================
DESCRIPTION = """
Core API for the PyTorch Model

### LLM Model
- Get all LLM models
- Get an LLM model by ID
- Run public chest X-ray Prediction by mode

### User - CRUD operations + auth flow
"""
API_TAGS_METADATA = [
    {
        "name": APITag.MODEL.value,
        "description": "Operations related to LLM models.",
    },
    {
        "name": APITag.USER.value,
        "description": "Operations related to users + auth flow.",
    },
]


def custom_generate_unique_id_function(route: APIRoute) -> str:
    """
    Generate a unique ID for the route.
    """
    return route.name


app = FastAPI(
    title="Core API",
    description=DESCRIPTION,
    docs_url=None,
    redoc_url=None,
    version="0.1.0",
    openapi_tags=API_TAGS_METADATA,
    generate_unique_id_function=custom_generate_unique_id_function,
)
configure_observability(app)

# =============================== CORS MIDDLEWARE ===============================
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_allowed_origins_tuple,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================== EXCEPTION HANDLER ===============================
add_exception_handlers(app)


# =============================== ROOT + DOCS ENDPOINT ===============================
@app.get("/")
async def get_root():
    """
    Root endpoint for the API.
    """
    return {"service": "core-api", "status": "ok"}


@app.get("/scalar", include_in_schema=False)
async def get_scalar_docs():
    """
    Adds an Scalar API reference to the API, so we can use it in the Scalar console.
    """
    if not app_settings.SCALAR_DOCS_ENABLED or app_settings.APP_ENVIRONMENT == "production":
        raise HTTPException(status_code=404, detail="Not found")

    return get_scalar_api_reference(
        openapi_url="/openapi.json",
        title="Core API",
    )


# =============================== ROUTERS ===============================
# Add all endpoints
app.include_router(master_router)
