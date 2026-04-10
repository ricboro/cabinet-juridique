from fastapi import APIRouter

from app.api.routes import clients, dossiers, actes, type_actes

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(clients.router)
api_router.include_router(dossiers.router)
api_router.include_router(actes.router)
api_router.include_router(type_actes.router)
