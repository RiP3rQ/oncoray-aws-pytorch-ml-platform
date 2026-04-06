from fastapi import APIRouter
from src.routers import kubernetes_router, model_router, user_router

# Single router to group all api routers
master_router = APIRouter()

master_router.include_router(kubernetes_router.router)
master_router.include_router(model_router.router)
master_router.include_router(user_router.router)
