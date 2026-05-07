"""
GDL Nexus — Módulo de Visibilidad Comercial
Sprint 2 - HU02: Ranking de zonas por visibilidad

La métrica de Visibilidad es diferente a la Factibilidad:
  - Factibilidad responde "¿puedo abrir aquí?" (incluye presupuesto)
  - Visibilidad responde "¿cuánta gente verá mi negocio aquí?" (independiente del costo)

Componentes de la Visibilidad:
  1. Tráfico peatonal ponderado por giro        (40%)
  2. Tráfico vehicular ponderado por giro        (25%)
  3. Conectividad de transporte público          (15%)
  4. Índice de densidad comercial complementaria (12%)  ← zonas con variedad atraen más visitas
  5. Saturación inversa del giro                  (8%)  ← demasiada competencia oculta el negocio
"""

from dataclasses import dataclass, field
from typing import Optional


# Pesos de afluencia por giro (mismo que factibilidad para consistencia)
_PESOS_GIRO: dict[str, dict[str, float]] = {
    "cafeteria":           {"peatonal": 0.70, "vehicular": 0.20, "transporte": 0.10},
    "restaurante":         {"peatonal": 0.50, "vehicular": 0.40, "transporte": 0.10},
    "retail_ropa":         {"peatonal": 0.60, "vehicular": 0.30, "transporte": 0.10},
    "consultorio_dental":  {"peatonal": 0.30, "vehicular": 0.50, "transporte": 0.20},
    "gimnasio":            {"peatonal": 0.20, "vehicular": 0.60, "transporte": 0.20},
    "farmacia":            {"peatonal": 0.60, "vehicular": 0.20, "transporte": 0.20},
    "barberia":            {"peatonal": 0.60, "vehicular": 0.30, "transporte": 0.10},
    "tienda_conveniencia": {"peatonal": 0.50, "vehicular": 0.30, "transporte": 0.20},
    "panaderia":           {"peatonal": 0.70, "vehicular": 0.20, "transporte": 0.10},
    "floristeria":         {"peatonal": 0.50, "vehicular": 0.40, "transporte": 0.10},
}

# Giros que se benefician de estar cerca de otros (complementariedad)
_GIROS_COMPLEMENTARIOS: dict[str, list[str]] = {
    "cafeteria":           ["restaurante", "panaderia", "retail_ropa"],
    "restaurante":         ["cafeteria", "retail_ropa", "floristeria"],
    "retail_ropa":         ["cafeteria", "restaurante", "barberia"],
    "consultorio_dental":  ["farmacia"],
    "gimnasio":            ["farmacia", "cafeteria"],
    "farmacia":            ["consultorio_dental", "tienda_conveniencia"],
    "barberia":            ["retail_ropa", "cafeteria"],
    "tienda_conveniencia": ["farmacia", "panaderia"],
    "panaderia":           ["cafeteria", "tienda_conveniencia"],
    "floristeria":         ["restaurante", "cafeteria"],
}


@dataclass
class ResultadoVisibilidad:
    zona_id: str
    zona_nombre: str
    lat: float
    lng: float
    score_visibilidad: float          # 0–100 score compuesto
    rank: int                         # posición 1=mejor
    afluencia_ponderada: int
    score_trafico_peatonal: float
    score_trafico_vehicular: float
    score_transporte: float
    score_complementariedad: float
    score_saturacion_inv: float       # saturación INVERSA: más score = menos saturado
    alertas: list[str] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)


def _score_trafico_peatonal(peatonal: int, giro: str) -> float:
    """Score 0-100 de tráfico peatonal ponderado por dependencia del giro."""
    w = _PESOS_GIRO.get(giro, {"peatonal": 0.5})["peatonal"]
    # Referencia: 20,000 peatones/día = score 100 para giro muy dependiente
    return round(min((peatonal * w / (20000 * 0.7)) * 100, 100), 2)


def _score_trafico_vehicular(vehicular: int, giro: str) -> float:
    """Score 0-100 de tráfico vehicular ponderado por dependencia del giro."""
    w = _PESOS_GIRO.get(giro, {"vehicular": 0.4})["vehicular"]
    # Referencia: 15,000 vehículos/día = score 100 para giro muy dependiente
    return round(min((vehicular * w / (15000 * 0.6)) * 100, 100), 2)


def _score_transporte(tp: int) -> float:
    """Score 0-100 de conectividad de transporte público (escala 0-10)."""
    return round(min(tp * 10, 100), 2)


def _score_complementariedad(giro: str, negocios_por_giro: dict) -> float:
    """
    Score 0-100 basado en cuántos negocios complementarios hay cerca.
    Una zona con variedad de giros afines atrae más flujo general.
    """
    complementarios = _GIROS_COMPLEMENTARIOS.get(giro, [])
    if not complementarios:
        return 50.0

    total_complementarios = sum(negocios_por_giro.get(g, 0) for g in complementarios)
    # Referencia: 30+ negocios complementarios = zona muy vibrante
    return round(min((total_complementarios / 30) * 100, 100), 2)


def _score_saturacion_inversa(giro: str, negocios_por_giro: dict, zona_saturada: bool) -> float:
    """
    Score 0-100 INVERSO a la saturación del giro propio.
    Demasiada competencia directa oculta visualmente el negocio.
    """
    num = negocios_por_giro.get(giro, 0)
    if zona_saturada and num > 40:
        return 5.0
    if num == 0:
        return 100.0
    if num <= 5:
        return 90.0
    if num <= 15:
        return 75.0
    if num <= 30:
        return 50.0
    if num <= 50:
        return 25.0
    return 10.0


def calcular_visibilidad_zona(zona: dict, giro: str) -> tuple[float, dict]:
    """
    Calcula el score de visibilidad para una zona dado un giro.
    Retorna: (score_total, scores_desglosados)
    """
    s_peat  = _score_trafico_peatonal(zona["afluencia_peatonal"], giro)
    s_veh   = _score_trafico_vehicular(zona["afluencia_vehicular"], giro)
    s_tp    = _score_transporte(zona["transporte_publico"])
    s_comp  = _score_complementariedad(giro, zona["negocios_por_giro"])
    s_sat   = _score_saturacion_inversa(giro, zona["negocios_por_giro"], zona["zona_saturada"])

    # Pesos fijos de la métrica de visibilidad
    total = (
        s_peat * 0.40 +
        s_veh  * 0.25 +
        s_tp   * 0.15 +
        s_comp * 0.12 +
        s_sat  * 0.08
    )

    return round(total, 2), {
        "trafico_peatonal":    s_peat,
        "trafico_vehicular":   s_veh,
        "transporte_publico":  s_tp,
        "complementariedad":   s_comp,
        "saturacion_inversa":  s_sat,
    }


def rankear_zonas_por_visibilidad(giro: str, datos: dict) -> list[ResultadoVisibilidad]:
    """
    HU02 - T02.03: Calcula y ordena todas las zonas por score de visibilidad.
    """
    resultados = []

    for zona in datos["zonas"]:
        score, scores = calcular_visibilidad_zona(zona, giro)

        # Afluencia ponderada bruta para contexto
        w = _PESOS_GIRO.get(giro, {"peatonal": 0.5, "vehicular": 0.4, "transporte": 0.1})
        afl_pond = int(
            zona["afluencia_peatonal"] * w["peatonal"] +
            zona["afluencia_vehicular"] * w["vehicular"] +
            zona["transporte_publico"] * 500 * w["transporte"]
        )

        alertas: list[str] = []
        insights: list[str] = []

        if scores["trafico_peatonal"] > 80:
            insights.append("Alto tráfico peatonal: ideal para negocios de impulso.")
        if scores["trafico_vehicular"] > 80:
            insights.append("Alta circulación vehicular: buena visibilidad de fachada.")
        if scores["complementariedad"] > 75:
            insights.append("Ecosistema comercial complementario: atrae flujo cruzado.")
        if scores["saturacion_inversa"] < 30:
            alertas.append("Alta competencia directa: tu negocio tendrá menos visibilidad individual.")
        if not zona["estacionamiento_disponible"]:
            alertas.append("Sin estacionamiento cercano: puede limitar visitas en auto.")

        resultados.append(ResultadoVisibilidad(
            zona_id=zona["id"],
            zona_nombre=zona["nombre"],
            lat=zona["lat"],
            lng=zona["lng"],
            score_visibilidad=score,
            rank=0,  # se asigna después del sort
            afluencia_ponderada=afl_pond,
            score_trafico_peatonal=scores["trafico_peatonal"],
            score_trafico_vehicular=scores["trafico_vehicular"],
            score_transporte=scores["transporte_publico"],
            score_complementariedad=scores["complementariedad"],
            score_saturacion_inv=scores["saturacion_inversa"],
            alertas=alertas,
            insights=insights,
        ))

    resultados.sort(key=lambda r: r.score_visibilidad, reverse=True)
    for i, r in enumerate(resultados):
        r.rank = i + 1

    return resultados


def visibilidad_a_dict(r: ResultadoVisibilidad) -> dict:
    return {
        "zona_id":           r.zona_id,
        "zona_nombre":       r.zona_nombre,
        "lat":               r.lat,
        "lng":               r.lng,
        "score_visibilidad": r.score_visibilidad,
        "rank":              r.rank,
        "afluencia_ponderada": r.afluencia_ponderada,
        "scores": {
            "trafico_peatonal":   r.score_trafico_peatonal,
            "trafico_vehicular":  r.score_trafico_vehicular,
            "transporte_publico": r.score_transporte,
            "complementariedad":  r.score_complementariedad,
            "saturacion_inversa": r.score_saturacion_inv,
        },
        "alertas":  r.alertas,
        "insights": r.insights,
    }
