"""
CaféTrace SV — Schemas de respuesta para el análisis de riesgo de deforestación.
"""

from typing import List
from uuid import UUID

from pydantic import BaseModel, Field


class DetalleAnioRiesgo(BaseModel):
    anio: int
    area_perdida_ha: float
    porcentaje_parcela: float = Field(
        ..., description="Porcentaje del área total de la parcela perdido ese año"
    )
    supera_umbral_absoluto: bool
    es_pico_anomalo: bool


class RiesgoDeforestacionOut(BaseModel):
    id_parcela: UUID
    nivel_riesgo: str = Field(..., description="'bajo' | 'medio' | 'alto'")
    explicacion: str
    linea_base_historica_ha: float = Field(
        ..., description="Mediana de pérdida anual histórica (años pre-2021)"
    )
    perdida_acumulada_ha: float = Field(
        ..., description="Suma de pérdida de cobertura desde 2021 (inclusive)"
    )
    porcentaje_acumulado_parcela: float = Field(
        ..., description="Pérdida acumulada desde 2021, como % del área total de la parcela"
    )
    anios_evaluados: List[DetalleAnioRiesgo]
