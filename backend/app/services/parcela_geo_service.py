"""
CaféTrace SV — Obtiene la geometría GeoJSON de una parcela por SQL directo
(sin ORM, según v0.2 del changelog), validando que pertenezca a la misma
organización del usuario autenticado (multi-tenancy, v0.7).

Cadena de relaciones usada para el filtro de organización:
    parcelas -> fincas -> productores -> usuarios -> organizaciones
"""

import json
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# NOTA: asumo que la PK de 'usuarios' es 'id_usuario', según el diagrama
# de tu base de datos. Ajusta si en tu esquema real es distinto.
_QUERY_PARCELA_CON_ORGANIZACION = text(
    """
    SELECT
        p.id_parcela,
        p.nombre,
        p.variedad_cafe,
        p.area_hectareas,
        ST_AsGeoJSON(p.geometria) AS geometria_geojson
    FROM parcelas p
    JOIN fincas f ON f.id_finca = p.id_finca
    JOIN productores pr ON pr.id_productor = f.id_productor
    JOIN usuarios u ON u.id_usuario = pr.id_usuario
    WHERE p.id_parcela = :id_parcela
      AND u.id_organizacion = (
          SELECT id_organizacion FROM usuarios WHERE id_usuario = :id_usuario_actual
      )
    """
)


async def obtener_geometria_parcela(
    db: AsyncSession, id_parcela: UUID, id_usuario_actual: UUID
) -> Optional[dict]:
    """
    Devuelve un dict con los datos de la parcela + su geometría en GeoJSON,
    solo si pertenece a la misma organización que el usuario autenticado.

    Devuelve None tanto si la parcela no existe como si pertenece a otra
    organización — a propósito, para no filtrar (mediante la diferencia de
    respuesta) qué parcelas existen en organizaciones ajenas.
    """
    resultado = await db.execute(
        _QUERY_PARCELA_CON_ORGANIZACION,
        {"id_parcela": id_parcela, "id_usuario_actual": id_usuario_actual},
    )
    fila = resultado.mappings().first()
    if fila is None:
        return None

    return {
        "id_parcela": fila["id_parcela"],
        "nombre": fila["nombre"],
        "variedad_cafe": fila["variedad_cafe"],
        "area_hectareas": float(fila["area_hectareas"]),
        "geometria": json.loads(fila["geometria_geojson"]),
    }
