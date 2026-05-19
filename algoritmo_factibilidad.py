"""
GDL Nexus - Algoritmo de Factibilidad (Fuerza Bruta)
Sprint 1 - HU01: T01.04

Enfoque: Fuerza Bruta
El algoritmo evalúa TODAS las zonas disponibles contra TODOS los criterios del usuario
sin ninguna optimización. Calcula un score de factibilidad ponderado para cada zona
y las ordena de mayor a menor.

Criterios de Factibilidad:
  1. Viabilidad Presupuestaria  → ¿Puede el usuario pagar la renta?
  2. Densidad de Competencia   → ¿Hay demasiados negocios del mismo giro?
  3. Score de Afluencia        → ¿Hay suficiente flujo de clientes potenciales?
  4. Compatibilidad NSE        → ¿El NSE de la zona coincide con el cliente objetivo?
  5. Plusvalía y Proyección    → ¿Es una zona en crecimiento?
"""

import json
import math
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class SemaforoColor(Enum):
    VERDE = "VERDE"       # Factibilidad >= 70%
    AMARILLO = "AMARILLO" # Factibilidad entre 40% y 69%
    ROJO = "ROJO"         # Factibilidad < 40%


@dataclass
class InputUsuario:
    """Datos de entrada del emprendedor."""
    giro: str                        # Tipo de negocio
    presupuesto_renta_mensual: float  # En pesos MXN
    metros_cuadrados_requeridos: float # m² del local
    nse_cliente_objetivo: list[str]   # ["A/B", "B", "B/C"] etc.
    importancia_afluencia: float = 1.0  # Peso 0.5 - 1.5 (por defecto 1.0)
    importancia_precio: float = 1.0     # Peso 0.5 - 1.5
    importancia_competencia: float = 1.0 # Peso 0.5 - 1.5


@dataclass
class ResultadoZona:
    """Resultado del análisis de factibilidad para una zona."""
    zona_id: str
    zona_nombre: str
    lat: float
    lng: float
    score_total: float            # 0.0 - 100.0
    semaforo: SemaforoColor
    descripcion_zona: str

    # Scores individuales (0-100 cada uno)
    score_presupuesto: float
    score_competencia: float
    score_afluencia: float
    score_nse: float
    score_plusvalia: float

    # Datos crudos para transparencia
    nse_zona: str
    renta_estimada: float
    negocios_mismo_giro: int
    afluencia_total: int
    renta_m2: float

    # Alertas y recomendaciones
    alertas: list[str] = field(default_factory=list)
    recomendaciones: list[str] = field(default_factory=list)

    # Estimado de retorno (meses para recuperar inversión inicial)
    meses_recuperacion_estimado: Optional[float] = None


def cargar_datos_zonas(ruta: str) -> dict:
    """T01.03: Carga los datos geo-económicos desde el archivo de datos."""
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


# ──────────────────────────────────────────────────────────────────────────────
# FUNCIONES DE SCORING INDIVIDUALES (usadas en el algoritmo brute-force)
# ──────────────────────────────────────────────────────────────────────────────

def calcular_score_presupuesto(
    presupuesto_usuario: float,
    metros_requeridos: float,
    renta_m2_zona: float
) -> tuple[float, float, list[str]]:
    """
    Evalúa si el presupuesto del usuario alcanza para la renta en la zona.
    Retorna: (score 0-100, renta_estimada, alertas)
    """
    alertas = []
    renta_estimada = metros_requeridos * renta_m2_zona

    if presupuesto_usuario <= 0:
        return 0.0, renta_estimada, ["Presupuesto inválido."]

    ratio = presupuesto_usuario / renta_estimada  # >1 = puede pagar

    if ratio >= 2.0:
        # Tiene el doble o más del presupuesto necesario → muy cómodo
        score = 100.0
    elif ratio >= 1.5:
        # Tiene 1.5x el presupuesto → holgado
        score = 90.0
    elif ratio >= 1.2:
        # Tiene 1.2x → justo pero viable
        score = 75.0
    elif ratio >= 1.0:
        # Exactamente al límite → viable pero sin margen
        score = 55.0
        alertas.append("Presupuesto justo al límite. Sin margen para imprevistos.")
    elif ratio >= 0.8:
        # Déficit del 20% → difícil
        score = 25.0
        alertas.append(f"Presupuesto insuficiente. La renta estimada es ${renta_estimada:,.0f}/mes.")
    else:
        # Déficit severo
        score = 0.0
        alertas.append(f"Presupuesto muy por debajo. Se necesitan ${renta_estimada:,.0f}/mes.")

    return round(score, 2), round(renta_estimada, 2), alertas


def calcular_score_competencia(
    giro: str,
    negocios_por_giro: dict,
    densidad_total: int,
    zona_saturada: bool
) -> tuple[float, int, list[str]]:
    """
    Evalúa la saturación del mercado para el giro específico del usuario.
    Menor competencia directa = mayor score.
    Retorna: (score 0-100, num_competidores, alertas)
    """
    alertas = []
    num_competidores = negocios_por_giro.get(giro, 0)

    # Ratio de competencia respecto al total de negocios de la zona
    if densidad_total > 0:
        ratio_saturacion_giro = num_competidores / densidad_total
    else:
        ratio_saturacion_giro = 0

    # Scoring inverso: más competidores = menos score
    # Umbrales calibrados empíricamente (fuerza bruta sin optimización)
    if zona_saturada and num_competidores > 40:
        score = 5.0
        alertas.append(f"Zona SATURADA: {num_competidores} competidores directos de '{giro}'.")
    elif num_competidores == 0:
        score = 100.0  # Oportunidad única, sin competencia
        alertas.append(f"Sin competencia directa de '{giro}' registrada. Valida en campo.")
    elif num_competidores <= 5:
        score = 95.0  # Muy baja competencia
    elif num_competidores <= 10:
        score = 85.0
    elif num_competidores <= 20:
        score = 70.0
    elif num_competidores <= 35:
        score = 50.0
        alertas.append(f"Competencia moderada-alta: {num_competidores} negocios similares.")
    elif num_competidores <= 50:
        score = 25.0
        alertas.append(f"Alta competencia: {num_competidores} negocios del mismo giro.")
    else:
        score = 10.0
        alertas.append(f"Competencia EXTREMA: {num_competidores} negocios de '{giro}'. Alto riesgo.")

    return round(score, 2), num_competidores, alertas


def calcular_score_afluencia(
    afluencia_peatonal: int,
    afluencia_vehicular: int,
    transporte_publico: int,
    giro: str
) -> tuple[float, int, list[str]]:
    """
    Evalúa el flujo de clientes potenciales según el giro.
    Algunos negocios dependen más del peatón (cafetería) otros del auto (gimnasio).
    Retorna: (score 0-100, afluencia_total_ponderada, alertas)
    """
    alertas = []

    # Pesos de afluencia por tipo de giro (heurística brute-force)
    PESOS_GIRO = {
        "cafeteria": {"peatonal": 0.7, "vehicular": 0.2, "transporte": 0.1},
        "restaurante": {"peatonal": 0.5, "vehicular": 0.4, "transporte": 0.1},
        "retail_ropa": {"peatonal": 0.6, "vehicular": 0.3, "transporte": 0.1},
        "consultorio_dental": {"peatonal": 0.3, "vehicular": 0.5, "transporte": 0.2},
        "gimnasio": {"peatonal": 0.2, "vehicular": 0.6, "transporte": 0.2},
        "farmacia": {"peatonal": 0.6, "vehicular": 0.2, "transporte": 0.2},
        "barberia": {"peatonal": 0.6, "vehicular": 0.3, "transporte": 0.1},
        "tienda_conveniencia": {"peatonal": 0.5, "vehicular": 0.3, "transporte": 0.2},
        "panaderia": {"peatonal": 0.7, "vehicular": 0.2, "transporte": 0.1},
        "floristeria": {"peatonal": 0.5, "vehicular": 0.4, "transporte": 0.1},
    }

    pesos = PESOS_GIRO.get(giro, {"peatonal": 0.5, "vehicular": 0.4, "transporte": 0.1})

    # Normalizar transporte público (0-10 → 0-5000 personas equivalentes)
    transporte_equiv = transporte_publico * 500

    afluencia_ponderada = (
        afluencia_peatonal * pesos["peatonal"] +
        afluencia_vehicular * pesos["vehicular"] +
        transporte_equiv * pesos["transporte"]
    )

    afluencia_total = int(afluencia_ponderada)

    # Scoring: normalizado contra 15,000 personas como "afluencia ideal"
    AFLUENCIA_IDEAL = 15000
    score_raw = (afluencia_ponderada / AFLUENCIA_IDEAL) * 100
    score = min(score_raw, 100.0)

    if score < 30:
        alertas.append("Afluencia baja. Considera estrategias de marketing activo.")
    elif score > 85:
        alertas.append("Alta afluencia. Excelente visibilidad natural.")

    return round(score, 2), afluencia_total, alertas


def calcular_score_nse(
    nse_zona: str,
    nse_cliente_objetivo: list[str]
) -> tuple[float, list[str]]:
    """
    Verifica si el NSE de la zona coincide con el perfil del cliente objetivo.
    Retorna: (score 0-100, alertas)
    """
    alertas = []

    # Jerarquía NSE (mayor índice = mayor NSE)
    JERARQUIA_NSE = ["D", "C/D", "C", "B/C", "B", "A/B", "A+"]

    nivel_zona = JERARQUIA_NSE.index(nse_zona) if nse_zona in JERARQUIA_NSE else 2

    max_score = 0.0
    for nse_obj in nse_cliente_objetivo:
        if nse_obj not in JERARQUIA_NSE:
            continue
        nivel_obj = JERARQUIA_NSE.index(nse_obj)
        diferencia = abs(nivel_zona - nivel_obj)

        if diferencia == 0:
            score_parcial = 100.0
        elif diferencia == 1:
            score_parcial = 75.0
        elif diferencia == 2:
            score_parcial = 40.0
        else:
            score_parcial = 10.0

        max_score = max(max_score, score_parcial)

    if max_score < 40:
        alertas.append(
            f"NSE de zona ({nse_zona}) no coincide con tu cliente objetivo {nse_cliente_objetivo}."
        )

    return round(max_score, 2), alertas


def calcular_score_plusvalia(plusvalia_score: float, zona_saturada: bool) -> tuple[float, list[str]]:
    """
    Evalúa el potencial de crecimiento y plusvalía de la zona.
    Retorna: (score 0-100, alertas)
    """
    alertas = []
    # plusvalia_score ya viene en escala 0-10
    score = (plusvalia_score / 10.0) * 100.0

    if zona_saturada:
        score *= 0.75  # Penalización por saturación
        alertas.append("Zona con alta densidad comercial (saturación). La plusvalía se ve afectada.")

    return round(score, 2), alertas


def calcular_meses_recuperacion(
    presupuesto_renta: float,
    afluencia_ponderada: int,
    nse_zona: str,
    datos_nse: dict
) -> Optional[float]:
    """
    Estimación muy simplificada (fuerza bruta) del tiempo de recuperación.
    Asume: ingreso_mensual ≈ afluencia * ticket_promedio * tasa_conversion
    """
    info_nse = datos_nse.get(nse_zona)
    if not info_nse:
        return None

    ticket_promedio = info_nse["ticket_promedio_gasto"]
    tasa_conversion = 0.08  # 8% de la afluencia se convierte en cliente (heurística bruta)

    # Inversión inicial estimada: 3 meses de renta + setup
    inversion_inicial_estimada = presupuesto_renta * 5

    ingreso_mensual_estimado = afluencia_ponderada * ticket_promedio * tasa_conversion
    gasto_mensual = presupuesto_renta * 1.4  # Renta + operación básica

    utilidad_mensual = ingreso_mensual_estimado - gasto_mensual

    if utilidad_mensual <= 0:
        return None  # No viable financieramente

    meses = inversion_inicial_estimada / utilidad_mensual
    return round(meses, 1)


# ──────────────────────────────────────────────────────────────────────────────
# ALGORITMO PRINCIPAL: FUERZA BRUTA
# ──────────────────────────────────────────────────────────────────────────────

def evaluar_factibilidad_brute_force(
    usuario: InputUsuario,
    datos: dict
) -> list[ResultadoZona]:
    """
    Algoritmo de factibilidad por FUERZA BRUTA.

    Complejidad: O(n * c) donde n = zonas, c = criterios
    Sin optimización: evalúa TODAS las zonas contra TODOS los criterios.

    Pesos de cada criterio (ponderados por preferencias del usuario):
      - Presupuesto:   30% (crítico, no negociable)
      - Competencia:   25%
      - Afluencia:     25%
      - NSE:           12%
      - Plusvalía:      8%
    """
    resultados = []

    # Pesos base (ajustados por preferencias del usuario)
    PESO_PRESUPUESTO = 0.30
    PESO_COMPETENCIA = 0.25 * usuario.importancia_competencia
    PESO_AFLUENCIA   = 0.25 * usuario.importancia_afluencia
    PESO_NSE         = 0.12
    PESO_PLUSVALIA   = 0.08

    # Normalizar pesos para que sumen 1.0
    suma_pesos = PESO_PRESUPUESTO + PESO_COMPETENCIA + PESO_AFLUENCIA + PESO_NSE + PESO_PLUSVALIA
    PESO_PRESUPUESTO /= suma_pesos
    PESO_COMPETENCIA /= suma_pesos
    PESO_AFLUENCIA   /= suma_pesos
    PESO_NSE         /= suma_pesos
    PESO_PLUSVALIA   /= suma_pesos

    datos_nse = datos.get("nse_rangos", {})

    # ── FUERZA BRUTA: iterar TODAS las zonas sin filtro previo ──
    for zona in datos["zonas"]:

        alertas_zona = []
        recomendaciones_zona = []

        # T01.04.1 - Score de Presupuesto
        s_presupuesto, renta_estimada, alertas_p = calcular_score_presupuesto(
            usuario.presupuesto_renta_mensual,
            usuario.metros_cuadrados_requeridos,
            zona["renta_m2"]
        )
        alertas_zona.extend(alertas_p)

        # T01.04.2 - Score de Competencia
        s_competencia, num_competidores, alertas_c = calcular_score_competencia(
            usuario.giro,
            zona["negocios_por_giro"],
            zona["densidad_negocios_total"],
            zona["zona_saturada"]
        )
        alertas_zona.extend(alertas_c)

        # T01.04.3 - Score de Afluencia
        s_afluencia, afluencia_total, alertas_a = calcular_score_afluencia(
            zona["afluencia_peatonal"],
            zona["afluencia_vehicular"],
            zona["transporte_publico"],
            usuario.giro
        )
        alertas_zona.extend(alertas_a)

        # T01.04.4 - Score NSE
        s_nse, alertas_n = calcular_score_nse(
            zona["nse"],
            usuario.nse_cliente_objetivo
        )
        alertas_zona.extend(alertas_n)

        # T01.04.5 - Score Plusvalía
        s_plusvalia, alertas_pv = calcular_score_plusvalia(
            zona["plusvalia_score"],
            zona["zona_saturada"]
        )
        alertas_zona.extend(alertas_pv)

        # ── SCORE TOTAL PONDERADO ──
        score_total = (
            s_presupuesto * PESO_PRESUPUESTO +
            s_competencia * PESO_COMPETENCIA +
            s_afluencia   * PESO_AFLUENCIA   +
            s_nse         * PESO_NSE         +
            s_plusvalia   * PESO_PLUSVALIA
        )
        score_total = round(score_total, 2)

        # T01.05 - Semáforo
        if score_total >= 70:
            semaforo = SemaforoColor.VERDE
        elif score_total >= 40:
            semaforo = SemaforoColor.AMARILLO
        else:
            semaforo = SemaforoColor.ROJO

        # Recomendaciones automáticas
        if s_presupuesto < 55:
            recomendaciones_zona.append(
                f"Considera aumentar tu presupuesto a ${renta_estimada * 1.2:,.0f}/mes o buscar local compartido."
            )
        if s_competencia > 85:
            recomendaciones_zona.append(
                "Aprovecha la baja competencia diferenciándote con calidad o nicho específico."
            )
        if s_afluencia < 40:
            recomendaciones_zona.append(
                "Refuerza presencia digital (Google Maps, redes sociales) para compensar baja afluencia."
            )
        if not zona["estacionamiento_disponible"]:
            recomendaciones_zona.append("Zona sin estacionamiento cercano. Evalúa impacto según tu cliente.")

        # Estimación de recuperación
        meses_rec = calcular_meses_recuperacion(
            renta_estimada,
            afluencia_total,
            zona["nse"],
            datos_nse
        )

        resultado = ResultadoZona(
            zona_id=zona["id"],
            zona_nombre=zona["nombre"],
            lat=zona["lat"],
            lng=zona["lng"],
            score_total=score_total,
            semaforo=semaforo,
            descripcion_zona=zona["descripcion"],
            score_presupuesto=s_presupuesto,
            score_competencia=s_competencia,
            score_afluencia=s_afluencia,
            score_nse=s_nse,
            score_plusvalia=s_plusvalia,
            nse_zona=zona["nse"],
            renta_estimada=renta_estimada,
            negocios_mismo_giro=num_competidores,
            afluencia_total=afluencia_total,
            renta_m2=zona["renta_m2"],
            alertas=alertas_zona,
            recomendaciones=recomendaciones_zona,
            meses_recuperacion_estimado=meses_rec
        )
        resultados.append(resultado)

    # Ordenar por score_total descendente (brute-force sort)
    resultados.sort(key=lambda r: r.score_total, reverse=True)

    return resultados


def resultado_a_dict(r: ResultadoZona) -> dict:
    """Serializa un ResultadoZona a diccionario JSON-compatible."""
    return {
        "zona_id": r.zona_id,
        "zona_nombre": r.zona_nombre,
        "lat": r.lat,
        "lng": r.lng,
        "score_total": r.score_total,
        "semaforo": r.semaforo.value,
        "descripcion_zona": r.descripcion_zona,
        "scores": {
            "presupuesto": r.score_presupuesto,
            "competencia": r.score_competencia,
            "afluencia": r.score_afluencia,
            "nse": r.score_nse,
            "plusvalia": r.score_plusvalia,
        },
        "datos_crudos": {
            "nse": r.nse_zona,
            "renta_estimada_mensual": r.renta_estimada,
            "negocios_mismo_giro": r.negocios_mismo_giro,
            "afluencia_ponderada": r.afluencia_total,
            "precio_m2": r.renta_m2,
        },
        "alertas": r.alertas,
        "recomendaciones": r.recomendaciones,
        "meses_recuperacion_estimado": r.meses_recuperacion_estimado,
    }


if __name__ == "__main__":
    # Demo rápido del algoritmo
    import os

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    datos = cargar_datos_zonas(os.path.join(base_dir, "data", "zonas_zmg.json"))

    usuario = InputUsuario(
        giro="cafeteria",
        presupuesto_renta_mensual=18000,
        metros_cuadrados_requeridos=50,
        nse_cliente_objetivo=["B", "A/B"],
        importancia_afluencia=1.2,
        importancia_competencia=1.1,
    )

    print(f"\n=== GDL NEXUS - Análisis de Factibilidad (Fuerza Bruta) ===")
    print(f"Giro: {usuario.giro} | Presupuesto: ${usuario.presupuesto_renta_mensual:,}/mes | {usuario.metros_cuadrados_requeridos}m²")
    print(f"NSE objetivo: {usuario.nse_cliente_objetivo}\n")

    resultados = evaluar_factibilidad_brute_force(usuario, datos)

    print(f"{'#':<3} {'Zona':<30} {'Score':>7} {'Semáforo':<10} {'Renta Est.':>12} {'Competidores':>13}")
    print("-" * 80)
    for i, r in enumerate(resultados, 1):
        semaforo_emoji = {"VERDE": "🟢", "AMARILLO": "🟡", "ROJO": "🔴"}[r.semaforo.value]
        print(
            f"{i:<3} {r.zona_nombre:<30} {r.score_total:>6.1f}% "
            f"{semaforo_emoji} {r.semaforo.value:<9} ${r.renta_estimada:>10,.0f} "
            f"{r.negocios_mismo_giro:>12}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# LOG DE EJECUCIÓN
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class LogEjecucion:
    """Registro detallado del proceso interno de cada algoritmo."""
    algoritmo: str
    zonas_total: int
    zonas_evaluadas_completo: int   # cuántas recibieron los 5 criterios
    zonas_podadas: int              # descartadas antes del score completo
    pasos: list[dict]               # registro paso a paso


# ──────────────────────────────────────────────────────────────────────────────
# VORAZ (Greedy)
# ──────────────────────────────────────────────────────────────────────────────

def evaluar_factibilidad_greedy(
    usuario: InputUsuario,
    datos: dict,
) -> tuple[list[ResultadoZona], LogEjecucion]:
    """
    Algoritmo voraz: aplica filtros baratos en orden de mayor poder discriminante
    antes de calcular el score completo.

    Orden de filtros:
      1. Presupuesto  — si ratio < 0.8 se descarta sin evaluar nada más
      2. Saturación   — si zona_saturada y competidores > 40, descartada
      3. NSE mínimo   — si la distancia NSE es máxima (diferencia > 3 niveles)
         con todos los NSE objetivo, descartada
      4. Score completo solo para las zonas supervivientes

    Complejidad: O(n) en el peor caso, sub-lineal si los filtros descartan zonas.
    """
    PESO_PRESUPUESTO = 0.30
    PESO_COMPETENCIA = 0.25 * usuario.importancia_competencia
    PESO_AFLUENCIA   = 0.25 * usuario.importancia_afluencia
    PESO_NSE         = 0.12
    PESO_PLUSVALIA   = 0.08
    suma_pesos = PESO_PRESUPUESTO + PESO_COMPETENCIA + PESO_AFLUENCIA + PESO_NSE + PESO_PLUSVALIA
    PESO_PRESUPUESTO /= suma_pesos
    PESO_COMPETENCIA /= suma_pesos
    PESO_AFLUENCIA   /= suma_pesos
    PESO_NSE         /= suma_pesos
    PESO_PLUSVALIA   /= suma_pesos

    datos_nse  = datos.get("nse_rangos", {})
    NSE_ORDEN  = ["D", "C/D", "C", "B/C", "B", "A/B", "A+"]
    resultados = []
    pasos      = []
    podadas    = 0
    evaluadas  = 0

    for zona in datos["zonas"]:
        nombre = zona["nombre"]

        # ── FILTRO 1: Presupuesto mínimo ──────────────────────────────────────
        renta_est = usuario.metros_cuadrados_requeridos * zona["renta_m2"]
        ratio_p   = usuario.presupuesto_renta_mensual / renta_est if renta_est > 0 else 0
        if ratio_p < 0.8:
            podadas += 1
            pasos.append({
                "zona": nombre, "paso": 1,
                "filtro": "Presupuesto",
                "accion": "PODADA",
                "razon": f"Ratio presupuesto/renta = {ratio_p:.2f} < 0.80",
            })
            continue

        # ── FILTRO 2: Zona saturada con exceso de competencia directa ─────────
        num_comp = zona["negocios_por_giro"].get(usuario.giro, 0)
        if zona["zona_saturada"] and num_comp > 40:
            podadas += 1
            pasos.append({
                "zona": nombre, "paso": 2,
                "filtro": "Saturacion",
                "accion": "PODADA",
                "razon": f"Zona saturada con {num_comp} competidores directos",
            })
            continue

        # ── FILTRO 3: NSE completamente incompatible ──────────────────────────
        idx_zona = NSE_ORDEN.index(zona["nse"]) if zona["nse"] in NSE_ORDEN else 2
        min_dist = min(
            abs(idx_zona - NSE_ORDEN.index(n))
            for n in usuario.nse_cliente_objetivo
            if n in NSE_ORDEN
        ) if usuario.nse_cliente_objetivo else 99
        if min_dist > 3:
            podadas += 1
            pasos.append({
                "zona": nombre, "paso": 3,
                "filtro": "NSE",
                "accion": "PODADA",
                "razon": f"NSE zona '{zona['nse']}' demasiado lejano al perfil objetivo",
            })
            continue

        # ── EVALUACIÓN COMPLETA para zonas que pasaron los filtros ───────────
        evaluadas += 1
        alertas_zona, recomendaciones_zona = [], []

        s_presupuesto, renta_estimada, ap = calcular_score_presupuesto(
            usuario.presupuesto_renta_mensual,
            usuario.metros_cuadrados_requeridos, zona["renta_m2"])
        alertas_zona.extend(ap)

        s_competencia, num_competidores, ac = calcular_score_competencia(
            usuario.giro, zona["negocios_por_giro"],
            zona["densidad_negocios_total"], zona["zona_saturada"])
        alertas_zona.extend(ac)

        s_afluencia, afluencia_total, aa = calcular_score_afluencia(
            zona["afluencia_peatonal"], zona["afluencia_vehicular"],
            zona["transporte_publico"], usuario.giro)
        alertas_zona.extend(aa)

        s_nse, an = calcular_score_nse(zona["nse"], usuario.nse_cliente_objetivo)
        alertas_zona.extend(an)

        s_plusvalia, apv = calcular_score_plusvalia(zona["plusvalia_score"], zona["zona_saturada"])
        alertas_zona.extend(apv)

        score_total = round(
            s_presupuesto * PESO_PRESUPUESTO + s_competencia * PESO_COMPETENCIA +
            s_afluencia   * PESO_AFLUENCIA   + s_nse         * PESO_NSE +
            s_plusvalia   * PESO_PLUSVALIA, 2)

        semaforo = (SemaforoColor.VERDE if score_total >= 70
                    else SemaforoColor.AMARILLO if score_total >= 40
                    else SemaforoColor.ROJO)

        pasos.append({
            "zona": nombre, "paso": "completo",
            "filtro": "—",
            "accion": "EVALUADA",
            "razon": f"Score total: {score_total}% → {semaforo.value}",
        })

        if s_presupuesto < 55:
            recomendaciones_zona.append(
                f"Considera aumentar tu presupuesto a ${renta_estimada * 1.2:,.0f}/mes o buscar local compartido.")
        if s_competencia > 85:
            recomendaciones_zona.append("Aprovecha la baja competencia diferenciándote con calidad o nicho específico.")
        if s_afluencia < 40:
            recomendaciones_zona.append("Refuerza presencia digital (Google Maps, redes sociales) para compensar baja afluencia.")
        if not zona["estacionamiento_disponible"]:
            recomendaciones_zona.append("Zona sin estacionamiento cercano. Evalúa impacto según tu cliente.")

        meses_rec = calcular_meses_recuperacion(renta_estimada, afluencia_total, zona["nse"], datos_nse)

        resultados.append(ResultadoZona(
            zona_id=zona["id"], zona_nombre=zona["nombre"],
            lat=zona["lat"], lng=zona["lng"],
            score_total=score_total, semaforo=semaforo,
            descripcion_zona=zona["descripcion"],
            score_presupuesto=s_presupuesto, score_competencia=s_competencia,
            score_afluencia=s_afluencia, score_nse=s_nse, score_plusvalia=s_plusvalia,
            nse_zona=zona["nse"], renta_estimada=renta_estimada,
            negocios_mismo_giro=num_competidores, afluencia_total=afluencia_total,
            renta_m2=zona["renta_m2"], alertas=alertas_zona,
            recomendaciones=recomendaciones_zona,
            meses_recuperacion_estimado=meses_rec,
        ))

    # Las zonas podadas no aparecen en el ranking; se agregan al final con score 0
    # para que el frontend pueda mostrarlas en el log pero no en el mapa
    resultados.sort(key=lambda r: r.score_total, reverse=True)

    log = LogEjecucion(
        algoritmo="Voraz (Greedy)",
        zonas_total=len(datos["zonas"]),
        zonas_evaluadas_completo=evaluadas,
        zonas_podadas=podadas,
        pasos=pasos,
    )
    return resultados, log


# ──────────────────────────────────────────────────────────────────────────────
# DIVIDE Y VENCERÁS
# ──────────────────────────────────────────────────────────────────────────────

def _construir_resultado_zona(zona: dict, usuario: InputUsuario, datos_nse: dict,
                               pesos: tuple) -> ResultadoZona:
    """Calcula el ResultadoZona completo para una zona. Reutilizable en D&V."""
    PESO_P, PESO_C, PESO_A, PESO_N, PESO_PV = pesos
    alertas, recs = [], []

    s_p, renta_est, ap = calcular_score_presupuesto(
        usuario.presupuesto_renta_mensual, usuario.metros_cuadrados_requeridos, zona["renta_m2"])
    alertas.extend(ap)

    s_c, num_comp, ac = calcular_score_competencia(
        usuario.giro, zona["negocios_por_giro"],
        zona["densidad_negocios_total"], zona["zona_saturada"])
    alertas.extend(ac)

    s_a, afl_total, aa = calcular_score_afluencia(
        zona["afluencia_peatonal"], zona["afluencia_vehicular"],
        zona["transporte_publico"], usuario.giro)
    alertas.extend(aa)

    s_n, an = calcular_score_nse(zona["nse"], usuario.nse_cliente_objetivo)
    alertas.extend(an)

    s_pv, apv = calcular_score_plusvalia(zona["plusvalia_score"], zona["zona_saturada"])
    alertas.extend(apv)

    score = round(s_p*PESO_P + s_c*PESO_C + s_a*PESO_A + s_n*PESO_N + s_pv*PESO_PV, 2)
    sem = (SemaforoColor.VERDE if score >= 70
           else SemaforoColor.AMARILLO if score >= 40
           else SemaforoColor.ROJO)

    if s_p < 55:
        recs.append(f"Considera aumentar tu presupuesto a ${renta_est * 1.2:,.0f}/mes o buscar local compartido.")
    if s_c > 85:
        recs.append("Aprovecha la baja competencia diferenciándote con calidad o nicho específico.")
    if s_a < 40:
        recs.append("Refuerza presencia digital (Google Maps, redes sociales) para compensar baja afluencia.")
    if not zona.get("estacionamiento_disponible", True):
        recs.append("Zona sin estacionamiento cercano. Evalúa impacto según tu cliente.")

    meses = calcular_meses_recuperacion(renta_est, afl_total, zona["nse"], datos_nse)

    return ResultadoZona(
        zona_id=zona["id"], zona_nombre=zona["nombre"],
        lat=zona["lat"], lng=zona["lng"],
        score_total=score, semaforo=sem, descripcion_zona=zona["descripcion"],
        score_presupuesto=s_p, score_competencia=s_c,
        score_afluencia=s_a, score_nse=s_n, score_plusvalia=s_pv,
        nse_zona=zona["nse"], renta_estimada=renta_est,
        negocios_mismo_giro=num_comp, afluencia_total=afl_total,
        renta_m2=zona["renta_m2"], alertas=alertas, recomendaciones=recs,
        meses_recuperacion_estimado=meses,
    )


def _dyv_recursivo(zonas: list[dict], usuario: InputUsuario,
                   datos_nse: dict, pesos: tuple,
                   pasos: list, profundidad: int) -> list[ResultadoZona]:
    """
    Divide el conjunto de zonas en mitades, evalúa cada mitad de forma
    independiente y fusiona ordenando por score_total descendente.

    Caso base: 1 o 2 zonas → evaluar directamente.
    """
    n = len(zonas)

    if n == 0:
        return []

    if n <= 2:
        # Caso base: evaluar cada zona directamente
        resultados = []
        for zona in zonas:
            r = _construir_resultado_zona(zona, usuario, datos_nse, pesos)
            pasos.append({
                "zona": zona["nombre"],
                "profundidad": profundidad,
                "accion": "EVALUADA (caso base)",
                "score": r.score_total,
            })
            resultados.append(r)
        resultados.sort(key=lambda r: r.score_total, reverse=True)
        return resultados

    # Dividir en dos mitades
    mid    = n // 2
    izq    = zonas[:mid]
    der    = zonas[mid:]

    pasos.append({
        "zona": f"[División prof={profundidad}]",
        "profundidad": profundidad,
        "accion": f"DIVIDIR: {[z['nombre'] for z in izq]} | {[z['nombre'] for z in der]}",
        "score": "—",
    })

    # Conquistar: resolver cada mitad recursivamente
    res_izq = _dyv_recursivo(izq, usuario, datos_nse, pesos, pasos, profundidad + 1)
    res_der = _dyv_recursivo(der, usuario, datos_nse, pesos, pasos, profundidad + 1)

    # Combinar: merge de dos listas ya ordenadas
    combinado = []
    i = j = 0
    while i < len(res_izq) and j < len(res_der):
        if res_izq[i].score_total >= res_der[j].score_total:
            combinado.append(res_izq[i]); i += 1
        else:
            combinado.append(res_der[j]); j += 1
    combinado.extend(res_izq[i:])
    combinado.extend(res_der[j:])

    pasos.append({
        "zona": f"[Combinación prof={profundidad}]",
        "profundidad": profundidad,
        "accion": "COMBINAR: ranking parcial = " + " > ".join(r.zona_nombre for r in combinado),
        "score": "—",
    })

    return combinado


def evaluar_factibilidad_divide_y_venceras(
    usuario: InputUsuario,
    datos: dict,
) -> tuple[list[ResultadoZona], LogEjecucion]:
    """
    Algoritmo Divide y Vencerás:
    Parte el catálogo en mitades recursivamente, evalúa cada subconjunto
    de forma independiente y fusiona los resultados ya ordenados (merge-sort).

    El resultado final es idéntico al brute-force en términos de scores,
    pero la estructura de resolución es jerárquica y visible en el log.

    Complejidad: O(n log n) por el merge — cada zona se evalúa exactamente
    una vez en el nivel hoja.
    """
    PESO_PRESUPUESTO = 0.30
    PESO_COMPETENCIA = 0.25 * usuario.importancia_competencia
    PESO_AFLUENCIA   = 0.25 * usuario.importancia_afluencia
    PESO_NSE         = 0.12
    PESO_PLUSVALIA   = 0.08
    suma_pesos = PESO_PRESUPUESTO + PESO_COMPETENCIA + PESO_AFLUENCIA + PESO_NSE + PESO_PLUSVALIA
    pesos = (
        PESO_PRESUPUESTO / suma_pesos,
        PESO_COMPETENCIA / suma_pesos,
        PESO_AFLUENCIA   / suma_pesos,
        PESO_NSE         / suma_pesos,
        PESO_PLUSVALIA   / suma_pesos,
    )

    datos_nse = datos.get("nse_rangos", {})
    zonas     = datos["zonas"]
    pasos     = []

    resultados = _dyv_recursivo(zonas, usuario, datos_nse, pesos, pasos, profundidad=0)

    log = LogEjecucion(
        algoritmo="Divide y Vencerás",
        zonas_total=len(zonas),
        zonas_evaluadas_completo=len(zonas),   # D&V evalúa todas
        zonas_podadas=0,
        pasos=pasos,
    )
    return resultados, log
