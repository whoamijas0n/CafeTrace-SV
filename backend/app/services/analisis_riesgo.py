"""
CaféTrace SV — Análisis de riesgo: pérdida de cobertura vegetal

Combina CUATRO señales sobre los años posteriores al corte EUDR (31/12/2020):

  1. Umbral absoluto por año: ¿un año individual supera un mínimo en ha?
     (0.5 ha, coincide con la definición de "bosque" de la EUDR)
  2. Pico anómalo: ¿un año individual es muy superior al comportamiento
     histórico de ESTA MISMA parcela (mediana de años pre-2021)?
  3. Acumulado: ¿la suma de pérdida desde 2021 supera cierto % del área
     total de la parcela? (cubre pérdida "poco a poco")
  4. Persistencia: ¿hay pérdida por encima del umbral en 2+ años distintos
     desde 2021?

Si (1+2 combinados), (3) o (4) se cumple -> riesgo "alto".
Si solo (1) o (2) se cumple de forma aislada -> riesgo "medio".
Si nada se cumple -> riesgo "bajo".

IMPORTANTE — límites de este análisis:
  - NO afirma causa humana ni certifica cumplimiento EUDR.
  - NO distingue pérdida por conversión de uso de suelo de pérdida por
    manejo agronómico normal (ej. poda de sombra en café).
  - La EUDR no define metodología estadística de "años base"; usamos
    mediana (no promedio) por ser resistente a un solo año atípico.
"""

import statistics
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from app.schemas.riesgo import DetalleAnioRiesgo, RiesgoDeforestacionOut

ANIO_CORTE_EUDR = 2021  # años >= este valor son "posteriores al 31/12/2020"

UMBRAL_ABSOLUTO_HA = 0.5       # coincide con la definición de "bosque" de la EUDR
MULTIPLICADOR_ANOMALIA = 2.5   # veces el baseline histórico para considerarse "pico"
UMBRAL_PORCENTAJE_ACUMULADO = 1.0  # % del área de la parcela, acumulado desde 2021
ANIOS_PERSISTENCIA = 2         # años distintos con pérdida sobre el umbral -> patrón persistente


def _completar_anios_faltantes(
    perdida_por_anio: Dict[int, float], anio_inicio: int, anio_fin: int
) -> Dict[int, float]:
    """
    GFW solo devuelve años con pérdida > 0. Completamos con 0.0 los años
    sin pérdida registrada, para que baseline y acumulados sean correctos.
    """
    return {anio: perdida_por_anio.get(anio, 0.0) for anio in range(anio_inicio, anio_fin + 1)}


def analizar_riesgo(
    id_parcela: UUID,
    resultados_gfw: List[dict],
    area_parcela_ha: float,
    anio_inicio: Optional[int] = None,
    anio_fin: Optional[int] = None,
) -> RiesgoDeforestacionOut:
    """
    resultados_gfw: lista que devuelve gfw_service.consultar_perdida_cobertura(),
    ej: [{"umd_tree_cover_loss__year": 2016, "area_ha": 22.8229}, ...]
    area_parcela_ha: parcelas.area_hectareas de la parcela evaluada.

    anio_inicio / anio_fin: si no se pasan, se calculan automáticamente
    (últimos 10 años hasta el año actual) para no tener que actualizar
    números hardcodeados con el paso del tiempo.
    """
    if area_parcela_ha <= 0:
        raise ValueError("area_parcela_ha debe ser mayor a 0")

    if anio_fin is None:
        anio_fin = datetime.now(timezone.utc).year
    if anio_inicio is None:
        anio_inicio = anio_fin - 10

    perdida_por_anio = {
        fila["umd_tree_cover_loss__year"]: fila["area_ha"] for fila in resultados_gfw
    }
    serie_completa = _completar_anios_faltantes(perdida_por_anio, anio_inicio, anio_fin)

    anios_historicos = {a: ha for a, ha in serie_completa.items() if a < ANIO_CORTE_EUDR}
    anios_recientes = {a: ha for a, ha in serie_completa.items() if a >= ANIO_CORTE_EUDR}

    linea_base = (
        statistics.median(anios_historicos.values()) if anios_historicos else 0.0
    )

    detalles: List[DetalleAnioRiesgo] = []
    for anio, area_ha in sorted(anios_recientes.items()):
        supera_umbral = area_ha > UMBRAL_ABSOLUTO_HA
        es_pico = (
            (linea_base > 0 and area_ha > linea_base * MULTIPLICADOR_ANOMALIA)
            or (linea_base == 0 and area_ha > UMBRAL_ABSOLUTO_HA)
        )
        detalles.append(
            DetalleAnioRiesgo(
                anio=anio,
                area_perdida_ha=area_ha,
                porcentaje_parcela=round((area_ha / area_parcela_ha) * 100, 4),
                supera_umbral_absoluto=supera_umbral,
                es_pico_anomalo=es_pico,
            )
        )

    perdida_acumulada = sum(anios_recientes.values())
    porcentaje_acumulado = (perdida_acumulada / area_parcela_ha) * 100

    ambos = [d for d in detalles if d.supera_umbral_absoluto and d.es_pico_anomalo]
    alguno = [d for d in detalles if d.supera_umbral_absoluto or d.es_pico_anomalo]
    anios_marcados = len([d for d in detalles if d.supera_umbral_absoluto])

    es_persistente = anios_marcados >= ANIOS_PERSISTENCIA
    supera_acumulado = porcentaje_acumulado >= UMBRAL_PORCENTAJE_ACUMULADO

    if ambos or es_persistente or supera_acumulado:
        nivel_riesgo = "alto"
        razones = []
        if ambos:
            anios_str = ", ".join(str(d.anio) for d in ambos)
            razones.append(
                f"pico anómalo en {anios_str} (supera umbral y comportamiento histórico)"
            )
        if es_persistente:
            razones.append(
                f"pérdida por encima del umbral en {anios_marcados} años distintos "
                "desde 2021 (patrón persistente)"
            )
        if supera_acumulado:
            razones.append(
                f"pérdida acumulada desde 2021 de {perdida_acumulada:.4f} ha "
                f"({porcentaje_acumulado:.2f}% del área de la parcela)"
            )
        explicacion = (
            "Riesgo alto: " + "; ".join(razones) + ". Requiere verificación adicional. "
            "Nota: este análisis no distingue entre pérdida por conversión de uso de "
            "suelo y pérdida por manejo agronómico normal (ej. poda de sombra en café)."
        )
    elif alguno:
        nivel_riesgo = "medio"
        anios_str = ", ".join(str(d.anio) for d in alguno)
        explicacion = (
            f"Se detectó pérdida de cobertura vegetal en {anios_str}, posterior al corte "
            "EUDR (31/12/2020), en un año aislado y sin patrón acumulado ni persistente. "
            "Se recomienda revisión."
        )
    else:
        nivel_riesgo = "bajo"
        explicacion = (
            "No se detectó pérdida de cobertura vegetal significativa posterior al "
            "31/12/2020 en esta parcela, según los datos disponibles."
        )

    return RiesgoDeforestacionOut(
        id_parcela=id_parcela,
        nivel_riesgo=nivel_riesgo,
        explicacion=explicacion,
        linea_base_historica_ha=linea_base,
        perdida_acumulada_ha=round(perdida_acumulada, 4),
        porcentaje_acumulado_parcela=round(porcentaje_acumulado, 4),
        anios_evaluados=detalles,
    )
