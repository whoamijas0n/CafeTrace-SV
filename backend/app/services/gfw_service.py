"""
CaféTrace SV — Cliente async para la API de Global Forest Watch (GFW).

Usa httpx en vez de requests porque los endpoints de FastAPI son async y
no queremos bloquear el event loop con una llamada HTTP síncrona.

Requiere:
    pip install httpx
    (agrégalo también a requirements.txt)

Requiere en app/core/config.py (Settings):
    GFW_API_KEY: str
Y en tu .env:
    GFW_API_KEY=tu_key_real
"""

from typing import List

import httpx

from app.core.config import settings

BASE_URL = "https://data-api.globalforestwatch.org"
DATASET = "umd_tree_cover_loss"


async def _obtener_version_mas_reciente(client: httpx.AsyncClient, dataset: str) -> str:
    """
    Consulta las versiones disponibles del dataset y devuelve la más
    reciente, para no hardcodear una versión que GFW puede actualizar.
    """
    response = await client.get(f"{BASE_URL}/dataset/{dataset}")
    response.raise_for_status()
    body = response.json()
    versiones = body["data"]["versions"]
    return versiones[-1]


async def consultar_perdida_cobertura(geometria: dict, anio_minimo: int = 2015) -> List[dict]:
    """
    Consulta pérdida de cobertura arbórea (hectáreas) por año, agregada
    dentro del polígono dado, desde anio_minimo en adelante.

    geometria: dict tipo {"type": "Polygon", "coordinates": [...]}
    Devuelve: [{"umd_tree_cover_loss__year": 2016, "area_ha": 22.8229}, ...]
    """
    if not settings.GFW_API_KEY:
        raise RuntimeError("Configura GFW_API_KEY en tu .env / app.core.config.Settings")

    async with httpx.AsyncClient(timeout=30.0) as client:
        version = await _obtener_version_mas_reciente(client, DATASET)

        sql = (
            "SELECT umd_tree_cover_loss__year, SUM(area__ha) AS area_ha "
            "FROM results "
            f"WHERE umd_tree_cover_loss__year >= {anio_minimo} "
            "GROUP BY umd_tree_cover_loss__year "
            "ORDER BY umd_tree_cover_loss__year"
        )

        response = await client.post(
            f"{BASE_URL}/dataset/{DATASET}/{version}/query/json",
            headers={"x-api-key": settings.GFW_API_KEY, "Content-Type": "application/json"},
            json={"sql": sql, "geometry": geometria},
        )
        response.raise_for_status()
        body = response.json()
        return body["data"]
