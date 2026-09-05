"""
CaféTrace SV — Endpoint de riesgo de deforestación por parcela.

GET /api/v1/parcelas/{id_parcela}/riesgo-deforestacion

Requiere JWT (Bearer Token). Solo devuelve resultado si la parcela
pertenece a la misma organización del usuario autenticado.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.riesgo import RiesgoDeforestacionOut
from app.services import gfw_service, parcela_geo_service
from app.services.analisis_riesgo import analizar_riesgo

router = APIRouter()


@router.get(
    "/{id_parcela}/riesgo-deforestacion",
    response_model=RiesgoDeforestacionOut,
    summary="Analiza el riesgo de deforestación histórica de una parcela",
)
async def obtener_riesgo_deforestacion(
    id_parcela: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RiesgoDeforestacionOut:
    """
    1. Busca la parcela (validando que sea de la organización del usuario).
    2. Consulta a Global Forest Watch la pérdida histórica de cobertura
       arbórea dentro de su polígono.
    3. Calcula un nivel de riesgo ('bajo' | 'medio' | 'alto') combinando
       umbral absoluto, pico anómalo, acumulado y persistencia.

    Este resultado NO certifica cumplimiento EUDR ni afirma causa humana
    de la pérdida detectada — solo señala qué parcelas requieren revisión.
    """
    parcela = await parcela_geo_service.obtener_geometria_parcela(
        db, id_parcela=id_parcela, id_usuario_actual=current_user.id
    )
    if parcela is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parcela no encontrada.",
        )

    resultados_gfw = await gfw_service.consultar_perdida_cobertura(parcela["geometria"])

    return analizar_riesgo(
        id_parcela=parcela["id_parcela"],
        resultados_gfw=resultados_gfw,
        area_parcela_ha=parcela["area_hectareas"],
    )
