"""
CaféTrace SV — Consulta a Global Forest Watch: pérdida de cobertura arbórea por año

Toma el GeoJSON de una parcela (el que genera plot_to_geojson.py) y consulta
el dataset 'umd_tree_cover_loss' de GFW para obtener, año por año, cuántas
hectáreas de cobertura arbórea se perdieron dentro de ese polígono.

Importante: esto NO determina causa (humana, natural, etc.) ni certifica
nada sobre EUDR. Es solo el dato crudo histórico — la interpretación de
"cambio significativo" / "posible deforestación" / "requiere verificación"
es lógica que construimos aparte, encima de estos números.

Requisitos:
    pip install requests python-dotenv

Variables de entorno esperadas (.env):
    GFW_API_KEY=tu_api_key

Uso:
    python plot_to_geojson.py <plot_id> > parcela.json
    python gfw_query.py parcela.json
"""

import json
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://data-api.globalforestwatch.org"
DATASET = "umd_tree_cover_loss"
API_KEY = os.getenv("GFW_API_KEY")


def get_latest_version(dataset: str) -> str:
    """
    Consulta las versiones disponibles del dataset y devuelve la más reciente.
    Evita hardcodear una versión que GFW puede ir actualizando con el tiempo.
    """
    response = requests.get(f"{BASE_URL}/dataset/{dataset}")
    response.raise_for_status()
    body = response.json()
    versions = body["data"]["versions"]
    return versions[-1]


def query_tree_cover_loss(geometry: dict, min_year: int = 2015) -> list:
    """
    Consulta pérdida de cobertura arbórea (hectáreas) por año, agregada
    dentro del polígono dado, desde min_year en adelante.

    'geometry' debe ser un dict tipo {"type": "Polygon", "coordinates": [...]}.
    """
    if not API_KEY:
        raise RuntimeError("Define GFW_API_KEY en tu .env")

    version = get_latest_version(DATASET)
    print(f"Usando dataset {DATASET} versión {version}")

    sql = (
        "SELECT umd_tree_cover_loss__year, SUM(area__ha) AS area_ha "
        "FROM results "
        f"WHERE umd_tree_cover_loss__year >= {min_year} "
        "GROUP BY umd_tree_cover_loss__year "
        "ORDER BY umd_tree_cover_loss__year"
    )

    response = requests.post(
        f"{BASE_URL}/dataset/{DATASET}/{version}/query/json",
        headers={"x-api-key": API_KEY, "Content-Type": "application/json"},
        json={"sql": sql, "geometry": geometry},
    )

    if not response.ok:
        print(f"\n--- Respuesta cruda ({response.status_code}) ---")
        print(response.text)
        print("--- fin respuesta cruda ---\n")

    response.raise_for_status()
    body = response.json()
    return body["data"]


if __name__ == "__main__":
    geojson_path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else input("Ruta al archivo GeoJSON de la parcela (Feature): ").strip()
    )

    with open(geojson_path, "r", encoding="utf-8") as f:
        parsed = json.load(f)

    # Aceptamos tanto un Feature completo (properties + geometry) como
    # una geometría pelada, para no depender de un solo formato de entrada.
    geometry = parsed["geometry"] if parsed.get("type") == "Feature" else parsed

    print("Consultando pérdida de cobertura arbórea en GFW...\n")
    results = query_tree_cover_loss(geometry)

    if not results:
        print("No se encontró pérdida de cobertura arbórea registrada en esta parcela.")
    else:
        print("Pérdida de cobertura arbórea por año (hectáreas):")
        for row in results:
            year = row["umd_tree_cover_loss__year"]
            area = row["area_ha"]
            print(f"  {year}: {area:.4f} ha")
