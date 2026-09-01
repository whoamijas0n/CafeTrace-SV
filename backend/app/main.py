from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.api.v1.api import api_router
from app.core.config import settings
from app.db.session import async_engine

# OpenAPI Tags metadata for structured Swagger documentation
tags_metadata = [
    {
        "name": "1. Autenticación & Usuarios",
        "description": "Registro de usuarios, login OAuth2 y obtención de tokens JWT Bearer.",
    },
    {
        "name": "2. Perfil de Productores",
        "description": "Gestión de perfiles de productores de café y cooperativas asociadas.",
    },
    {
        "name": "3. Fincas Cafetaleras",
        "description": "Registro y administración de fincas con estadísticas espaciales agregadas.",
    },
    {
        "name": "4. Parcelas & GIS Espacial",
        "description": "Trazado de parcelas (tablones), cálculo geodésico de área y exportación GeoJSON RFC 7946 para MapLibre GL.",
    },
    {
        "name": "5. Monitoreo del Sistema",
        "description": "Health checks y estado de conectividad con la base de datos PostGIS.",
    },
]

# Initialize FastAPI application
app = FastAPI(
    title=f"{settings.PROJECT_NAME} — API",
    description="""
# ☕ CaféTrace SV — Plataforma Geoespacial de Trazabilidad & EUDR

Bienvenido a la API REST de **CaféTrace SV**, el backend de interoperabilidad y trazabilidad agrícola para el café salvadoreño con miras al cumplimiento de la normativa **EUDR (Reglamento UE 2023/1115)**.

---

### 🗺️ Especificaciones Geoespaciales:
* **CRS**: WGS84 (`EPSG:4326`).
* **Formato**: GeoJSON RFC 7946 estricto con orden `[longitud, latitud]`.
* **Cálculo de Área**: Geodésico en PostGIS sobre elipsoide (`ST_Area(geometry::geography) / 10000.0`).
* **Delimitación Nacional**: Coordenadas validadas para la República de El Salvador.

### 🔐 Seguridad:
* Autenticación basada en **JWT Bearer Tokens**.
* Para interactuar con los endpoints protegidos, haz login en `/api/v1/auth/login` y autoriza tu sesión en el botón **Authorize** superior.
    """,
    version="1.0.0",
    openapi_tags=tags_metadata,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Configure CORS Middleware for Next.js 14 frontend and development clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/health",
    tags=["5. Monitoreo del Sistema"],
    status_code=status.HTTP_200_OK,
    summary="Verificación del estado del servicio",
    description="Comprueba la salud operativa del backend y la conectividad a la base de datos PostgreSQL/PostGIS.",
)
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint returning system status, timestamp, and database connectivity.
    """
    db_status = "connected"
    postgis_version = "unknown"

    try:
        async with async_engine.connect() as conn:
            result = await conn.execute(text("SELECT PostGIS_Version();"))
            row = result.first()
            if row:
                postgis_version = str(row[0])
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy" if "error" not in db_status else "degraded",
        "service": settings.PROJECT_NAME,
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": db_status,
        "postgis_version": postgis_version,
    }


# Mount API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)
