from fastapi import APIRouter
from app.api.v1.endpoints import auth, farms, plots, producers

api_router = APIRouter()

# Group all module endpoints with semantic OpenAPI tags
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["1. Autenticación & Usuarios"],
)
api_router.include_router(
    producers.router,
    prefix="/producers",
    tags=["2. Perfil de Productores"],
)
api_router.include_router(
    farms.router,
    prefix="/farms",
    tags=["3. Fincas Cafetaleras"],
)
api_router.include_router(
    plots.router,
    prefix="/plots",
    tags=["4. Parcelas & GIS Espacial"],
)
