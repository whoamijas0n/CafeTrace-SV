"""
CaféTrace SV — Análisis de riesgo: pérdida de cobertura vegetal (v2)

Toma la serie anual de pérdida de cobertura arbórea (la que devuelve
gfw_query.query_tree_cover_loss()) más el área total de la parcela, y
calcula un nivel de riesgo combinando CUATRO señales sobre los años
posteriores al corte EUDR (31/12/2020):

  1. Umbral absoluto por año: ¿un año individual supera un mínimo en ha?
  2. Pico anómalo: ¿un año individual es muy superior al comportamiento
     histórico de ESTA MISMA parcela (mediana de años pre-2021)?
  3. Acumulado: ¿la suma de pérdida desde 2021 supera cierto % del área
     total de la parcela? (cubre pérdida "poco a poco" que nunca dispara
     el umbral de un solo año)
  4. Persistencia: ¿hay pérdida por encima del umbral en 2 o más años
     distintos desde 2021? (un patrón repetido pesa más que un evento
     aislado, aunque ninguno individualmente sea "anómalo")

Si CUALQUIERA de (1+2 combinados), (3) o (4) se cumple -> riesgo "alto".
Si solo (1) o (2) se cumple de forma aislada -> riesgo "medio".
Si nada se cumple -> riesgo "bajo".

IMPORTANTE — límites de este análisis:
  - NO afirma causa humana ni certifica cumplimiento EUDR. Solo etiqueta
    "pérdida de cobertura vegetal" / "cambio significativo" / "requiere
    verificación" para que un humano lo revise después.
  - NO distingue pérdida por conversión de uso de suelo de pérdida por
    manejo agronómico normal — en café de sombra, podar árboles de sombra
    también reduce la cobertura que detecta el satélite. Este algoritmo
    señala DÓNDE mirar, no QUÉ pasó.
  - La EUDR no define ninguna metodología estadística de "años base"; el
    uso de mediana (no promedio) para el baseline histórico es una
    decisión de diseño nuestra, elegida por ser resistente a un solo año
    atípico (ej. una tormenta puntual) que de otro modo inflaría un
    promedio y ocultaría eventos recientes que sí ameritan revisión.
  - Pendiente de verificar: el dataset umd_tree_cover_loss puede tener un
    campo de umbral de cobertura de dosel (canopy density) filtrable. Si
    existe, valdría la pena alinearlo al 10% que usa la definición de
    "bosque" de la EUDR — no lo agrego aún porque no confirmé el campo
    exacto en la documentación del dataset.
"""

import statistics
from typing import Dict, List

from pydantic import BaseModel, Field

EUDR_CUTOFF_YEAR = 2021  # años >= este valor son "posteriores al 31/12/2020"

# 0.5 ha no es arbitrario: coincide con la definición de "bosque" de la EUDR
# (tierra > 0.5 ha, árboles > 5m, cobertura de dosel > 10%).
ABSOLUTE_THRESHOLD_HA = 0.5

# Cuántas veces el baseline histórico (mediana) se considera "pico" en un año dado.
ANOMALY_MULTIPLIER = 2.5

# Pérdida ACUMULADA desde el corte EUDR, como % del área total de la parcela,
# que por sí sola basta para marcar riesgo alto — cubre pérdida "poco a poco".
CUMULATIVE_PCT_THRESHOLD = 1.0

# Si la parcela registra pérdida por encima del umbral en 2+ años distintos
# desde el corte, se considera un patrón persistente -> riesgo alto.
PERSISTENT_YEAR_COUNT = 2


class YearRiskDetail(BaseModel):
    year: int
    area_ha: float
    pct_of_plot_area: float = Field(
        ..., description="Porcentaje del área total de la parcela perdido ese año"
    )
    exceeds_absolute_threshold: bool
    is_anomalous_peak: bool


class RiskResult(BaseModel):
    risk_level: str = Field(..., description="'bajo' | 'medio' | 'alto'")
    explanation: str
    historical_baseline_ha: float = Field(
        ..., description="Mediana de pérdida anual histórica (pre-2021)"
    )
    cumulative_loss_ha: float = Field(
        ..., description="Suma de pérdida de cobertura desde 2021 (inclusive)"
    )
    cumulative_pct_of_plot: float = Field(
        ..., description="Pérdida acumulada desde 2021, como % del área total de la parcela"
    )
    years_evaluated: List[YearRiskDetail]


def _fill_missing_years(
    loss_by_year: Dict[int, float], start_year: int, end_year: int
) -> Dict[int, float]:
    """
    GFW solo devuelve años con pérdida > 0. Para calcular baseline y
    acumulados correctos, completamos con 0.0 los años sin pérdida
    registrada en el rango pedido.
    """
    return {year: loss_by_year.get(year, 0.0) for year in range(start_year, end_year + 1)}


def analyze_risk(
    gfw_results: List[dict],
    plot_area_ha: float,
    start_year: int = 2015,
    end_year: int = 2025,
) -> RiskResult:
    """
    gfw_results: la lista que devuelve gfw_query.query_tree_cover_loss(),
    ej: [{"umd_tree_cover_loss__year": 2016, "area_ha": 22.8229}, ...]
    plot_area_ha: área total de la parcela (Plot.area_hectares), usada
    para expresar la pérdida como porcentaje relativo, no solo hectáreas
    absolutas.
    """
    if plot_area_ha <= 0:
        raise ValueError("plot_area_ha debe ser mayor a 0")

    loss_by_year = {
        row["umd_tree_cover_loss__year"]: row["area_ha"] for row in gfw_results
    }
    full_series = _fill_missing_years(loss_by_year, start_year, end_year)

    historical_years = {y: ha for y, ha in full_series.items() if y < EUDR_CUTOFF_YEAR}
    recent_years = {y: ha for y, ha in full_series.items() if y >= EUDR_CUTOFF_YEAR}

    # Mediana, no promedio: un solo año con pérdida excepcional no debe
    # "acostumbrar" al modelo a considerar eso normal.
    historical_baseline = (
        statistics.median(historical_years.values()) if historical_years else 0.0
    )

    details: List[YearRiskDetail] = []
    for year, area_ha in sorted(recent_years.items()):
        exceeds_threshold = area_ha > ABSOLUTE_THRESHOLD_HA
        is_peak = (
            (historical_baseline > 0 and area_ha > historical_baseline * ANOMALY_MULTIPLIER)
            or (historical_baseline == 0 and area_ha > ABSOLUTE_THRESHOLD_HA)
        )
        details.append(
            YearRiskDetail(
                year=year,
                area_ha=area_ha,
                pct_of_plot_area=round((area_ha / plot_area_ha) * 100, 4),
                exceeds_absolute_threshold=exceeds_threshold,
                is_anomalous_peak=is_peak,
            )
        )

    cumulative_loss = sum(recent_years.values())
    cumulative_pct = (cumulative_loss / plot_area_ha) * 100

    triggered_both = [d for d in details if d.exceeds_absolute_threshold and d.is_anomalous_peak]
    triggered_either = [d for d in details if d.exceeds_absolute_threshold or d.is_anomalous_peak]
    flagged_years_count = len([d for d in details if d.exceeds_absolute_threshold])

    is_persistent = flagged_years_count >= PERSISTENT_YEAR_COUNT
    exceeds_cumulative = cumulative_pct >= CUMULATIVE_PCT_THRESHOLD

    if triggered_both or is_persistent or exceeds_cumulative:
        risk_level = "alto"
        reasons = []
        if triggered_both:
            years_str = ", ".join(str(d.year) for d in triggered_both)
            reasons.append(
                f"pico anómalo en {years_str} (supera umbral y comportamiento histórico)"
            )
        if is_persistent:
            reasons.append(
                f"pérdida por encima del umbral en {flagged_years_count} años distintos "
                "desde 2021 (patrón persistente)"
            )
        if exceeds_cumulative:
            reasons.append(
                f"pérdida acumulada desde 2021 de {cumulative_loss:.4f} ha "
                f"({cumulative_pct:.2f}% del área de la parcela)"
            )
        explanation = (
            "Riesgo alto: " + "; ".join(reasons) + ". Requiere verificación adicional. "
            "Nota: este análisis no distingue entre pérdida por conversión de uso de "
            "suelo y pérdida por manejo agronómico normal (ej. poda de sombra en café)."
        )
    elif triggered_either:
        risk_level = "medio"
        years_str = ", ".join(str(d.year) for d in triggered_either)
        explanation = (
            f"Se detectó pérdida de cobertura vegetal en {years_str}, posterior al corte "
            "EUDR (31/12/2020), en un año aislado y sin patrón acumulado ni persistente. "
            "Se recomienda revisión."
        )
    else:
        risk_level = "bajo"
        explanation = (
            "No se detectó pérdida de cobertura vegetal significativa posterior al "
            "31/12/2020 en esta parcela, según los datos disponibles."
        )

    return RiskResult(
        risk_level=risk_level,
        explanation=explanation,
        historical_baseline_ha=historical_baseline,
        cumulative_loss_ha=round(cumulative_loss, 4),
        cumulative_pct_of_plot=round(cumulative_pct, 4),
        years_evaluated=details,
    )


if __name__ == "__main__":
    # Los datos reales que ya obtuviste corriendo gfw_query.py sobre la parcela de prueba
    sample_results = [
        {"umd_tree_cover_loss__year": 2016, "area_ha": 22.8229},
        {"umd_tree_cover_loss__year": 2017, "area_ha": 0.1492},
        {"umd_tree_cover_loss__year": 2018, "area_ha": 1.9392},
        {"umd_tree_cover_loss__year": 2022, "area_ha": 0.5221},
        {"umd_tree_cover_loss__year": 2023, "area_ha": 0.5221},
        {"umd_tree_cover_loss__year": 2025, "area_ha": 1.1933},
    ]
    sample_plot_area_ha = 120.3  # ~área aproximada del polígono de prueba usado antes

    result = analyze_risk(sample_results, plot_area_ha=sample_plot_area_ha)

    print(f"Nivel de riesgo: {result.risk_level.upper()}")
    print(f"Baseline histórico (mediana, pre-2021): {result.historical_baseline_ha:.4f} ha/año")
    print(
        f"Acumulado desde 2021: {result.cumulative_loss_ha:.4f} ha "
        f"({result.cumulative_pct_of_plot:.2f}% del área de la parcela)\n"
    )
    print(f"{result.explanation}\n")
    print("Detalle por año evaluado (2021 en adelante):")
    for d in result.years_evaluated:
        flags = []
        if d.exceeds_absolute_threshold:
            flags.append("supera umbral")
        if d.is_anomalous_peak:
            flags.append("pico anómalo")
        flags_str = ", ".join(flags) if flags else "sin alertas"
        print(f"  {d.year}: {d.area_ha:.4f} ha ({d.pct_of_plot_area:.3f}% de la parcela) -> {flags_str}")
