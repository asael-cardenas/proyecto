"""
GDL Nexus — Módulo de Filtro y Comparación de Zonas
Sprint 3 - HU03: Filtro por tipo de negocio
Sprint 3 - HU04: Comparación lado a lado de zonas

HU03 — FiltroGiro:
  Filtra zonas según si son buenas para un giro concreto, evaluando:
  - Baja saturación del giro propio (menos competencia directa)
  - Alta presencia de giros complementarios (más flujo general)
  - NSE compatible con el ticket promedio del giro

HU04 — ComparacionZonas:
  Dado un conjunto de zona_ids, genera una ficha comparativa completa
  con todos los indicadores normalizados para decisión lado a lado.
"""

from dataclasses import dataclass, field
from typing import Optional

from backend import (
    InputUsuario,
    calcular_score_presupuesto,
    calcular_score_competencia,
    calcular_score_afluencia,
    calcular_score_nse,
    calcular_score_plusvalia,
    calcular_meses_recuperacion,
    SemaforoColor,
)
from visibilidad import calcular_visibilidad_zona


# ── HU03: FILTRO POR GIRO ─────────────────────────────────────────────────────

# NSE mínimo recomendado por giro (según ticket promedio)
_NSE_MINIMO_GIRO: dict[str, list[str]] = {
    "cafeteria":           ["B", "A/B", "A+"],
    "restaurante":         ["B/C", "B", "A/B", "A+"],
    "retail_ropa":         ["B", "A/B", "A+"],
    "consultorio_dental":  ["B", "A/B", "A+"],
    "gimnasio":            ["B/C", "B", "A/B", "A+"],
    "farmacia":            ["C", "B/C", "B", "A/B", "A+"],
    "barberia":            ["C", "B/C", "B", "A/B"],
    "tienda_conveniencia": ["C/D", "C", "B/C", "B", "A/B"],
    "panaderia":           ["C", "B/C", "B", "A/B"],
    "floristeria":         ["B/C", "B", "A/B", "A+"],
}

_NSE_JERARQUIA = ["D", "C/D", "C", "B/C", "B", "A/B", "A+"]


@dataclass
class ResultadoFiltroGiro:
    zona_id: str
    zona_nombre: str
    lat: float
    lng: float
    giro: str
    apto: bool                        # True si la zona es recomendable para el giro
    score_aptitud: float              # 0-100
    num_competidores: int
    score_saturacion: float           # score INVERSO: alto = poca competencia
    score_complementariedad: float
    score_nse_giro: float             # compatibilidad NSE con el giro
    razon: str                        # resumen en lenguaje natural
    recomendaciones: list[str] = field(default_factory=list)


def filtrar_zonas_por_giro(giro: str, datos: dict) -> list[ResultadoFiltroGiro]:
    """
    HU03 - T03.03: Recomienda zonas para un giro específico evaluando
    saturación, complementariedad y compatibilidad NSE del giro.
    """
    nse_ideales = _NSE_MINIMO_GIRO.get(giro, ["B/C", "B", "A/B"])
    resultados = []

    for zona in datos["zonas"]:
        num_comp = zona["negocios_por_giro"].get(giro, 0)

        # Score de saturación inverso (HU03: T03.03)
        if zona["zona_saturada"] and num_comp > 40:
            s_sat = 5.0
        elif num_comp == 0:
            s_sat = 100.0
        elif num_comp <= 5:
            s_sat = 92.0
        elif num_comp <= 15:
            s_sat = 75.0
        elif num_comp <= 30:
            s_sat = 50.0
        elif num_comp <= 50:
            s_sat = 22.0
        else:
            s_sat = 8.0

        # Score de complementariedad — mismo que visibilidad
        from visibilidad import _score_complementariedad
        s_comp = _score_complementariedad(giro, zona["negocios_por_giro"])

        # Score de compatibilidad NSE con el giro (¿puede pagar el cliente el producto?)
        idx_zona = _NSE_JERARQUIA.index(zona["nse"]) if zona["nse"] in _NSE_JERARQUIA else 2
        max_s_nse = 0.0
        for nse_ideal in nse_ideales:
            if nse_ideal not in _NSE_JERARQUIA:
                continue
            idx_ideal = _NSE_JERARQUIA.index(nse_ideal)
            diff = abs(idx_zona - idx_ideal)
            s = 100.0 if diff == 0 else 75.0 if diff == 1 else 40.0 if diff == 2 else 10.0
            max_s_nse = max(max_s_nse, s)

        # Score de aptitud compuesto
        score_aptitud = round(s_sat * 0.50 + s_comp * 0.30 + max_s_nse * 0.20, 2)
        apto = score_aptitud >= 55 and not (zona["zona_saturada"] and num_comp > 40)

        # Razón en lenguaje natural
        if num_comp == 0:
            razon = f"Sin competidores de '{giro}' registrados. Oportunidad de primer entrante."
        elif score_aptitud >= 75:
            razon = f"Baja competencia ({num_comp}) y buen ecosistema comercial complementario."
        elif score_aptitud >= 55:
            razon = f"Competencia moderada ({num_comp}). Viable con diferenciación clara."
        elif zona["zona_saturada"] and num_comp > 40:
            razon = f"Zona saturada con {num_comp} competidores directos. Muy difícil destacar."
        else:
            razon = f"Alta competencia ({num_comp} negocios similares). Riesgo elevado."

        recs = []
        if s_comp > 70:
            recs.append("Ecosistema comercial activo: aprovecha el flujo cruzado de giros complementarios.")
        if max_s_nse < 50:
            recs.append(f"El NSE de la zona ({zona['nse']}) puede no coincidir con el ticket de tu giro.")
        if num_comp == 0:
            recs.append("Valida en campo: la ausencia de datos no garantiza ausencia de competidores.")

        resultados.append(ResultadoFiltroGiro(
            zona_id=zona["id"],
            zona_nombre=zona["nombre"],
            lat=zona["lat"],
            lng=zona["lng"],
            giro=giro,
            apto=apto,
            score_aptitud=score_aptitud,
            num_competidores=num_comp,
            score_saturacion=s_sat,
            score_complementariedad=s_comp,
            score_nse_giro=max_s_nse,
            razon=razon,
            recomendaciones=recs,
        ))

    resultados.sort(key=lambda r: r.score_aptitud, reverse=True)
    return resultados


def filtro_giro_a_dict(r: ResultadoFiltroGiro) -> dict:
    return {
        "zona_id":   r.zona_id,
        "zona_nombre": r.zona_nombre,
        "lat": r.lat,
        "lng": r.lng,
        "giro":      r.giro,
        "apto":      r.apto,
        "score_aptitud": r.score_aptitud,
        "num_competidores": r.num_competidores,
        "scores": {
            "saturacion":        r.score_saturacion,
            "complementariedad": r.score_complementariedad,
            "nse_giro":          r.score_nse_giro,
        },
        "razon":           r.razon,
        "recomendaciones": r.recomendaciones,
    }


# ── HU04: COMPARACIÓN DE ZONAS ────────────────────────────────────────────────

@dataclass
class FichaComparacion:
    zona_id: str
    zona_nombre: str
    nse: str
    renta_m2: float
    # Scores normalizados 0-100 para comparación directa
    score_factibilidad: float
    score_visibilidad: float
    score_aptitud_giro: float
    score_presupuesto: float
    score_competencia: float
    score_afluencia: float
    score_nse: float
    score_plusvalia: float
    # Datos crudos
    renta_estimada: float
    num_competidores: int
    afluencia_ponderada: int
    meses_recuperacion: Optional[float]
    semaforo: str
    descripcion: str


def comparar_zonas(
    zona_ids: list[str],
    usuario: InputUsuario,
    datos: dict,
) -> list[FichaComparacion]:
    """
    HU04 - T04.03: Genera fichas comparativas completas para un conjunto de zonas.
    Normaliza todos los indicadores en la misma escala 0-100 para
    facilitar la decisión lado a lado.
    """
    from algoritmo_factibilidad import evaluar_factibilidad_brute_force, resultado_a_dict
    from visibilidad import rankear_zonas_por_visibilidad, visibilidad_a_dict
    from comparacion import filtrar_zonas_por_giro, filtro_giro_a_dict

    # Ejecutar los tres análisis completos
    todos_fact = {r.zona_id: r for r in evaluar_factibilidad_brute_force(usuario, datos)}
    todos_vis  = {r.zona_id: r for r in rankear_zonas_por_visibilidad(usuario.giro, datos)}
    todos_filtro = {r.zona_id: r for r in filtrar_zonas_por_giro(usuario.giro, datos)}

    zonas_index = {z["id"]: z for z in datos["zonas"]}
    datos_nse   = datos.get("nse_rangos", {})

    fichas = []
    for zid in zona_ids:
        if zid not in zonas_index:
            continue
        zona = zonas_index[zid]
        fact = todos_fact.get(zid)
        vis  = todos_vis.get(zid)
        filtro = todos_filtro.get(zid)

        if not fact or not vis or not filtro:
            continue

        fichas.append(FichaComparacion(
            zona_id=zid,
            zona_nombre=zona["nombre"],
            nse=zona["nse"],
            renta_m2=zona["renta_m2"],
            score_factibilidad=fact.score_total,
            score_visibilidad=vis.score_visibilidad,
            score_aptitud_giro=filtro.score_aptitud,
            score_presupuesto=fact.score_presupuesto,
            score_competencia=fact.score_competencia,
            score_afluencia=fact.score_afluencia,
            score_nse=fact.score_nse,
            score_plusvalia=fact.score_plusvalia,
            renta_estimada=fact.renta_estimada,
            num_competidores=fact.negocios_mismo_giro,
            afluencia_ponderada=fact.afluencia_total,
            meses_recuperacion=fact.meses_recuperacion_estimado,
            semaforo=fact.semaforo.value,
            descripcion=zona["descripcion"],
        ))

    # Ordenar por factibilidad por defecto
    fichas.sort(key=lambda f: f.score_factibilidad, reverse=True)
    return fichas


def comparacion_a_dict(f: FichaComparacion) -> dict:
    return {
        "zona_id":    f.zona_id,
        "zona_nombre": f.zona_nombre,
        "nse":        f.nse,
        "renta_m2":   f.renta_m2,
        "semaforo":   f.semaforo,
        "descripcion": f.descripcion,
        "scores": {
            "factibilidad":  f.score_factibilidad,
            "visibilidad":   f.score_visibilidad,
            "aptitud_giro":  f.score_aptitud_giro,
            "presupuesto":   f.score_presupuesto,
            "competencia":   f.score_competencia,
            "afluencia":     f.score_afluencia,
            "nse":           f.score_nse,
            "plusvalia":     f.score_plusvalia,
        },
        "datos_crudos": {
            "renta_estimada":    f.renta_estimada,
            "num_competidores":  f.num_competidores,
            "afluencia_ponderada": f.afluencia_ponderada,
            "meses_recuperacion": f.meses_recuperacion,
        },
    }
