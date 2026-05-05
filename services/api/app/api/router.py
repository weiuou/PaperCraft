from fastapi import APIRouter

from app.api.routes import projects, tasks

api_router = APIRouter(prefix="/api")
api_router.include_router(projects.router)
api_router.include_router(tasks.router)
