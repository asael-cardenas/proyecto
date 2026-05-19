"""
GDL Nexus — Análisis Unificado
Combina los cuatro módulos de análisis en un único score por zona:
  1. Factibilidad   (40%) — presupuesto, competencia, afluencia, NSE, plusvalía
  2. Visibilidad    (25%) — tráfico peatonal/vehicular, transporte, complementariedad
  3. Aptitud giro   (20%) — saturación, complementariedad, NSE mínimo del giro
  4. Posición rel.  (15%) — qué tan buena es esta zona vs. el resto del conjunto

El usuario puede ajustar los cuatro pesos con sliders (0.5–1.5×).
El algoritmo de evaluación (brute_force | greedy | divide_y_venceras) también es configurable.
"""

from dataclasses import dataclass, field
from typing import Optional

from algoritmo_factibilidad import (
    InputUsuario,
    calcular_score_presupuesto,
    calcular_score_competencia,
    calcular_score_afluencia,
    calcular_score_nse,
    calcular_score_plusvalia,
    calcular_meses_recuperacion,
    SemaforoColor,
    LogEjecucion,
    evaluar_factibilidad_brute_force,
    evaluar_factibilidad_greedy,
    evaluar_factibilidad_divide_y_venceras,
)
from visibilidad import calcular_visibilidad_zona
from comparacion import _NSE_MINIMO_GIRO, _NSE_JERARQUIA
from visibilidad import _score_complementariedad


# ── MODELO DE SALIDA ──────────────────────────────────────────────────────────

@dataclass
class ResultadoUnificado:
    """Score unificado de una zona combinando los cuatro análisis."""
    zona_id:     str
    zona_nombre: str
    lat:         float
    lng:         float
    nse_zona:    str

    # Score final
    score_unificado: float          # 0–100 ponderado de los cuatro componentes
    semaforo:        SemaforoColor

    # Cuatro componentes principales
    score_factibilidad: float
    score_visibilidad:  float
    score_aptitud_giro: float
    score_posicion_rel: float       # calculado post-hoc vs. el conjunto

    # Sub-scores de factibilidad (transparencia)
    sub_presupuesto: float
    sub_competencia: float
    sub_afluencia:   float
    sub_nse:         float
    sub_plusvalia:   float

    # Sub-scores de visibilidad (transparencia)
    sub_trafico_peatonal:  float
    sub_trafico_vehicular: float
    sub_transporte:        float
    sub_complementariedad: float
    sub_saturacion_inv:    float

    # Datos crudos
    renta_estimada:      float
    negocios_mismo_giro: int
    afluencia_ponderada: int
    apto_para_giro:      bool
    razon_giro:          str
    meses_recuperacion:  Optional[float]

    # Narrativa
    alertas:         list[str] = field(default_factory=list)
    recomendaciones: list[str] = field(default_factory=list)


# ── HELPERS INTERNOS ──────────────────────────────────────────────────────────

def _score_aptitud_giro(zona: dict, giro: str) -> tuple[float, bool, str]:
    """
    Calcula la aptitud de una zona para el giro (lógica de HU03).
    Retorna: (score, apto, razon)
    """
    nse_ideales = _NSE_MINIMO_GIRO.get(giro, ["B/C", "B", "A/B"])
    num_comp    = zona["negocios_por_giro"].get(giro, 0)

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

    s_comp   = _score_complementariedad(giro, zona["negocios_por_giro"])
    idx_zona = _NSE_JERARQUIA.index(zona["nse"]) if zona["nse"] in _NSE_JERARQUIA else 2
    max_nse  = 0.0
    for nse_ideal in nse_ideales:
        if nse_ideal not in _NSE_JERARQUIA:
            continue
        diff    = abs(idx_zona - _NSE_JERARQUIA.index(nse_ideal))
        max_nse = max(max_nse, 100. if diff==0 else 75. if diff==1 else 40. if diff==2 else 10.)

    score_aptitud = round(s_sat * 0.50 + s_comp * 0.30 + max_nse * 0.20, 2)
    apto = score_aptitud >= 55 and not (zona["zona_saturada"] and num_comp > 40)

    if num_comp == 0:
        razon = f"Sin competidores de '{giro}' registrados. Oportunidad de primer entrante."
    elif score_aptitud >= 75:
        razon = f"Baja competencia ({num_comp}) y buen ecosistema complementario."
    elif score_aptitud >= 55:
        razon = f"Competencia moderada ({num_comp}). Viable con diferenciación clara."
    elif zona["zona_saturada"] and num_comp > 40:
        razon = f"Zona saturada: {num_comp} competidores directos. Difícil destacar."
    else:
        razon = f"Alta competencia ({num_comp} negocios similares). Riesgo elevado."

    return score_aptitud, apto, razon


def _calcular_posicion_relativa(scores: list[float]) -> list[float]:
    """
    Normaliza una lista de scores al rango 0–100 según
    el mínimo y máximo del propio conjunto.
    Todas las zonas quedan contextualizadas entre sí.
    """
    mn, mx = min(scores), max(scores)
    if mx == mn:
        return [50.0] * len(scores)
    return [round((s - mn) / (mx - mn) * 100, 2) for s in scores]


def _normalizar_pesos(w_f, w_v, w_a, w_p) -> tuple[float, float, float, float]:
    total = w_f + w_v + w_a + w_p
    return w_f/total, w_v/total, w_a/total, w_p/total


# ── ALGORITMO UNIFICADO PRINCIPAL ─────────────────────────────────────────────

def evaluar_unificado(
    usuario:            InputUsuario,
    datos:              dict,
    peso_factibilidad:  float = 1.0,   # 0.5 – 1.5
    peso_visibilidad:   float = 1.0,
    peso_aptitud_giro:  float = 1.0,
    peso_posicion_rel:  float = 1.0,
    algoritmo:          str   = "brute_force",
) -> tuple[list[ResultadoUnificado], Optional[LogEjecucion]]:
    """
    Evalúa todas las zonas con los cuatro análisis combinados.

    Pesos base antes de ajuste por sliders:
      factibilidad  40%
      visibilidad   25%
      aptitud_giro  20%
      posicion_rel  15%
    """
    BASE_F, BASE_V, BASE_A, BASE_P = 0.40, 0.25, 0.20, 0.15
    WF, WV, WA, WP = _normalizar_pesos(
        BASE_F * peso_factibilidad,
        BASE_V * peso_visibilidad,
        BASE_A * peso_aptitud_giro,
        BASE_P * peso_posicion_rel,
    )

    datos_nse = datos.get("nse_rangos", {})

    # ── Pesos de factibilidad (internos al módulo) ────────────────────────────
    PESO_P = 0.30; PESO_C = 0.25 * usuario.importancia_competencia
    PESO_AFL = 0.25 * usuario.importancia_afluencia; PESO_N = 0.12; PESO_PV = 0.08
    suma = PESO_P + PESO_C + PESO_AFL + PESO_N + PESO_PV
    PESO_P /= suma; PESO_C /= suma; PESO_AFL /= suma; PESO_N /= suma; PESO_PV /= suma

    # ── Ejecutar algoritmo de factibilidad (para el log y los sub-scores) ─────
    log_obj = None
    if algoritmo == "greedy":
        fact_resultados, log_obj = evaluar_factibilidad_greedy(usuario, datos)
    elif algoritmo == "divide_y_venceras":
        fact_resultados, log_obj = evaluar_factibilidad_divide_y_venceras(usuario, datos)
    else:
        fact_resultados = evaluar_factibilidad_brute_force(usuario, datos)

    # Indexar por zona_id para acceso O(1)
    fact_idx = {r.zona_id: r for r in fact_resultados}

    # ── Calcular los cuatro scores por zona ───────────────────────────────────
    parciales: list[dict] = []

    for zona in datos["zonas"]:
        zid = zona["id"]

        # 1. Factibilidad — reutilizar resultado ya calculado
        fr = fact_idx.get(zid)
        if fr:
            s_fact   = fr.score_total
            s_pres   = fr.score_presupuesto
            s_comp   = fr.score_competencia
            s_afl    = fr.score_afluencia
            s_nse    = fr.score_nse
            s_pv     = fr.score_plusvalia
            renta_est = fr.renta_estimada
            num_comp  = fr.negocios_mismo_giro
            afl_pond  = fr.afluencia_total
            meses     = fr.meses_recuperacion_estimado
            alertas   = list(fr.alertas)
            recs      = list(fr.recomendaciones)
        else:
            # Zona podada por el voraz — calcular factibilidad mínima
            sp, renta_est, ap = calcular_score_presupuesto(
                usuario.presupuesto_renta_mensual, usuario.metros_cuadrados_requeridos, zona["renta_m2"])
            sc, num_comp, ac  = calcular_score_competencia(
                usuario.giro, zona["negocios_por_giro"], zona["densidad_negocios_total"], zona["zona_saturada"])
            sa, afl_pond, aa  = calcular_score_afluencia(
                zona["afluencia_peatonal"], zona["afluencia_vehicular"], zona["transporte_publico"], usuario.giro)
            sn, an = calcular_score_nse(zona["nse"], usuario.nse_cliente_objetivo)
            spv, apv = calcular_score_plusvalia(zona["plusvalia_score"], zona["zona_saturada"])
            s_fact = round(sp*PESO_P + sc*PESO_C + sa*PESO_AFL + sn*PESO_N + spv*PESO_PV, 2)
            s_pres, s_comp, s_afl, s_nse, s_pv = sp, sc, sa, sn, spv
            alertas = ap + ac + aa + an + apv
            meses = calcular_meses_recuperacion(renta_est, afl_pond, zona["nse"], datos_nse)
            recs = []

        # 2. Visibilidad
        s_vis, vis_scores = calcular_visibilidad_zona(zona, usuario.giro)

        # 3. Aptitud giro
        s_apt, apto, razon_giro = _score_aptitud_giro(zona, usuario.giro)

        # Recomendaciones adicionales del análisis unificado
        if not apto and not any("competidores" in r for r in recs):
            recs.append(razon_giro)
        if vis_scores["complementariedad"] > 75 and not any("complementario" in r for r in recs):
            recs.append("Ecosistema comercial activo: aprovecha el flujo cruzado de giros afines.")
        if not zona["estacionamiento_disponible"]:
            alertas.append("Sin estacionamiento cercano.")

        parciales.append({
            "zona":        zona,
            "s_fact":      s_fact,
            "s_vis":       s_vis,
            "s_apt":       s_apt,
            "s_pres":      s_pres,   "s_comp":  s_comp,  "s_afl":  s_afl,
            "s_nse":       s_nse,    "s_pv":    s_pv,
            "vis":         vis_scores,
            "renta_est":   renta_est, "num_comp": num_comp, "afl_pond": afl_pond,
            "apto":        apto,      "razon":    razon_giro,
            "meses":       meses,
            "alertas":     alertas,   "recs":     recs,
        })

    # ── Posición relativa — normalizar factibilidad vs. el conjunto ───────────
    scores_fact = [p["s_fact"] for p in parciales]
    pos_rel     = _calcular_posicion_relativa(scores_fact)

    # ── Score unificado final ─────────────────────────────────────────────────
    resultados: list[ResultadoUnificado] = []

    for p, s_pos in zip(parciales, pos_rel):
        score_u = round(
            p["s_fact"] * WF +
            p["s_vis"]  * WV +
            p["s_apt"]  * WA +
            s_pos       * WP,
            2
        )
        sem = (SemaforoColor.VERDE    if score_u >= 70 else
               SemaforoColor.AMARILLO if score_u >= 40 else
               SemaforoColor.ROJO)

        zona = p["zona"]
        resultados.append(ResultadoUnificado(
            zona_id=zona["id"], zona_nombre=zona["nombre"],
            lat=zona["lat"],    lng=zona["lng"],
            nse_zona=zona["nse"],
            score_unificado=score_u, semaforo=sem,
            score_factibilidad=p["s_fact"],
            score_visibilidad=p["s_vis"],
            score_aptitud_giro=p["s_apt"],
            score_posicion_rel=s_pos,
            sub_presupuesto=p["s_pres"], sub_competencia=p["s_comp"],
            sub_afluencia=p["s_afl"],   sub_nse=p["s_nse"],
            sub_plusvalia=p["s_pv"],
            sub_trafico_peatonal=p["vis"]["trafico_peatonal"],
            sub_trafico_vehicular=p["vis"]["trafico_vehicular"],
            sub_transporte=p["vis"]["transporte_publico"],
            sub_complementariedad=p["vis"]["complementariedad"],
            sub_saturacion_inv=p["vis"]["saturacion_inversa"],
            renta_estimada=p["renta_est"],
            negocios_mismo_giro=p["num_comp"],
            afluencia_ponderada=p["afl_pond"],
            apto_para_giro=p["apto"],
            razon_giro=p["razon"],
            meses_recuperacion=p["meses"],
            alertas=p["alertas"],
            recomendaciones=p["recs"],
        ))

    resultados.sort(key=lambda r: r.score_unificado, reverse=True)
    return resultados, log_obj


def unificado_a_dict(r: ResultadoUnificado) -> dict:
    return {
        "zona_id":     r.zona_id,
        "zona_nombre": r.zona_nombre,
        "lat":         r.lat,
        "lng":         r.lng,
        "nse_zona":    r.nse_zona,
        "score_unificado":   r.score_unificado,
        "semaforo":          r.semaforo.value,
        # Cuatro componentes
        "scores_principales": {
            "factibilidad":  r.score_factibilidad,
            "visibilidad":   r.score_visibilidad,
            "aptitud_giro":  r.score_aptitud_giro,
            "posicion_rel":  r.score_posicion_rel,
        },
        # Sub-scores de factibilidad
        "scores_factibilidad": {
            "presupuesto": r.sub_presupuesto,
            "competencia": r.sub_competencia,
            "afluencia":   r.sub_afluencia,
            "nse":         r.sub_nse,
            "plusvalia":   r.sub_plusvalia,
        },
        # Sub-scores de visibilidad
        "scores_visibilidad": {
            "trafico_peatonal":  r.sub_trafico_peatonal,
            "trafico_vehicular": r.sub_trafico_vehicular,
            "transporte":        r.sub_transporte,
            "complementariedad": r.sub_complementariedad,
            "saturacion_inv":    r.sub_saturacion_inv,
        },
        # Datos crudos
        "datos_crudos": {
            "renta_estimada_mensual": r.renta_estimada,
            "negocios_mismo_giro":    r.negocios_mismo_giro,
            "afluencia_ponderada":    r.afluencia_ponderada,
            "apto_para_giro":         r.apto_para_giro,
            "razon_giro":             r.razon_giro,
            "meses_recuperacion":     r.meses_recuperacion,
        },
        "alertas":         r.alertas,
        "recomendaciones": r.recomendaciones,
    }
