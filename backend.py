import json
import math
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class SemaforoColor(Enum):
    VERDE = "VERDE"
    AMARILLO = "AMARILLO"
    ROJO = "ROJO"


@dataclass
class InputUsuario:
    giro: str                        
    presupuesto_renta_mensual: float
    metros_cuadrados_requeridos: float 
    nse_cliente_objetivo: list[str]  
    importancia_afluencia: float = 1.0 
    importancia_precio: float = 1.0    
    importancia_competencia: float = 1.0


@dataclass
class ResultadoZona:
    zona_id: str
    zona_nombre: str
    lat: float
    lng: float
    score_total: float           
    semaforo: SemaforoColor
    descripcion_zona: str

    score_presupuesto: float
    score_competencia: float
    score_afluencia: float
    score_nse: float
    score_plusvalia: float

    nse_zona: str
    renta_estimada: float
    negocios_mismo_giro: int
    afluencia_total: int
    renta_m2: float

    alertas: list[str] = field(default_factory=list)
    recomendaciones: list[str] = field(default_factory=list)

    meses_recuperacion_estimado: Optional[float] = None


def cargar_datos_zonas(ruta: str) -> dict:
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)

def calcular_score_presupuesto(
    presupuesto_usuario: float,
    metros_requeridos: float,
    renta_m2_zona: float
) -> tuple[float, float, list[str]]:
    alertas = []
    renta_estimada = metros_requeridos * renta_m2_zona

    if presupuesto_usuario <= 0:
        return 0.0, renta_estimada, ["Presupuesto inválido."]

    ratio = presupuesto_usuario / renta_estimada  # >1 = puede pagar

    if ratio >= 2.0:
        score = 100.0
    elif ratio >= 1.5:
        score = 90.0
    elif ratio >= 1.2:
        score = 75.0
    elif ratio >= 1.0:
        score = 55.0
        alertas.append("Presupuesto justo al límite. Sin margen para imprevistos.")
    elif ratio >= 0.8:
        score = 25.0
        alertas.append(f"Presupuesto insuficiente. La renta estimada es ${renta_estimada:,.0f}/mes.")
    else:
        score = 0.0
        alertas.append(f"Presupuesto muy por debajo. Se necesitan ${renta_estimada:,.0f}/mes.")

    return round(score, 2), round(renta_estimada, 2), alertas


def calcular_score_competencia(
    giro: str,
    negocios_por_giro: dict,
    densidad_total: int,
    zona_saturada: bool
) -> tuple[float, int, list[str]]:
    
    alertas = []
    num_competidores = negocios_por_giro.get(giro, 0)

    if densidad_total > 0:
        ratio_saturacion_giro = num_competidores / densidad_total
    else:
        ratio_saturacion_giro = 0
    if zona_saturada and num_competidores > 40:
        score = 5.0
        alertas.append(f"Zona SATURADA: {num_competidores} competidores directos de '{giro}'.")
    elif num_competidores == 0:
        score = 100.0 
        alertas.append(f"Sin competencia directa de '{giro}' registrada. Valida en campo.")
    elif num_competidores <= 5:
        score = 95.0 
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
    alertas = []
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

    transporte_equiv = transporte_publico * 500

    afluencia_ponderada = (
        afluencia_peatonal * pesos["peatonal"] +
        afluencia_vehicular * pesos["vehicular"] +
        transporte_equiv * pesos["transporte"]
    )

    afluencia_total = int(afluencia_ponderada)

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

    alertas = []

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




def evaluar_factibilidad_FB(
    usuario: InputUsuario,
    datos: dict
) -> list[ResultadoZona]:
    
    resultados = []

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

    datos_nse = datos.get("nse_rangos", {})
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
    import os

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    datos = cargar_datos_zonas(os.path.join(base_dir,"algoritmos","zonas_zmg.json"))

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

    resultados = evaluar_factibilidad_FB(usuario, datos)

    print(f"{'#':<3} {'Zona':<30} {'Score':>7} {'Semáforo':<10} {'Renta Est.':>12} {'Competidores':>13}")
    print("-" * 80)
    for i, r in enumerate(resultados, 1):
        semaforo_emoji = {"VERDE", "AMARILLO", "ROJO"}[r.semaforo.value]
        print(
            f"{i:<3} {r.zona_nombre:<30} {r.score_total:>6.1f}% "
            f"{semaforo_emoji} {r.semaforo.value:<9} ${r.renta_estimada:>10,.0f} "
            f"{r.negocios_mismo_giro:>12}"
        )
