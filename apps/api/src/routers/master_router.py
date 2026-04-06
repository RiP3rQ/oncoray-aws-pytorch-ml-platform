from fastapi import APIRouter
from src.routers import model_router

# Single router to group all api routers
master_router = APIRouter()

master_router.include_router(model_router.router)
