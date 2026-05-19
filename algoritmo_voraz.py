import os
from dataclasses import dataclass, field

# === IMPORTACIONES DEL BACKEND EXISTENTE ===
from backend import InputUsuario, ResultadoZona, evaluar_factibilidad_FB, cargar_datos_zonas

@dataclass
class PortafolioVoraz:
    zonas_seleccionadas: list = field(default_factory=list)
    presupuesto_total_asignado: float = 0.0
    presupuesto_utilizado: float = 0.0
    presupuesto_remanente: float = 0.0
    score_acumulado_total: float = 0.0


def construir_portafolio_voraz(
    usuario: InputUsuario,
    datos: dict,
    presupuesto_global_expansion: float
) -> PortafolioVoraz:
    """
    Desarrolla la estrategia de Selección Voraz (Greedy) para un portafolio de inversión.
    """
    # 1. Evaluamos la factibilidad individual de todas las zonas usando el backend existente
    zonas_evaluadas = evaluar_factibilidad_FB(usuario, datos)
    
    # 2. Estructuramos los elementos candidatos con su respectivo Índice de Eficiencia Comercial (IEC)
    candidatos = []
    for zona in zonas_evaluadas:
        costo = zona.renta_estimada
        beneficio = zona.score_total
        
        iec = beneficio / costo if costo > 0 else 0.0
        candidatos.append({
            "zona": zona,
            "costo": costo,
            "beneficio": beneficio,
            "iec": iec
        })
    
    # 3. PASO VORAZ: Ordenar candidatos de mayor a menor eficiencia (IEC)
    candidatos.sort(key=lambda x: x["iec"], reverse=True)
    
    # 4. Selección secuencial
    portafolio = PortafolioVoraz(
        presupuesto_total_asignado=presupuesto_global_expansion,
        presupuesto_remanente=presupuesto_global_expansion
    )
    
    for c in candidatos:
        costo_zona = c["costo"]
        if costo_zona <= portafolio.presupuesto_remanente:
            portafolio.zonas_seleccionadas.append(c["zona"])
            portafolio.presupuesto_utilizado += costo_zona
            portafolio.presupuesto_remanente -= costo_zona
            portafolio.score_acumulado_total += c["beneficio"]
            
            c["zona"].recomendaciones.append(
                f"Seleccionada en portafolio por alta eficiencia costo/beneficio (IEC: {c['iec']:.5f})."
            )
            
    return portafolio


if __name__ == "__main__":
    # Localización directa del JSON en la misma carpeta raíz
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ruta_json = os.path.join(base_dir, "zonas_zmg.json")
    
    try:
        datos_zonas = cargar_datos_zonas(ruta_json)
    except FileNotFoundError:
        datos_zonas = cargar_datos_zonas("zonas_zmg.json")

    perfil_usuario = InputUsuario(
        giro="cafeteria",
        presupuesto_renta_mensual=15000,
        metros_cuadrados_requeridos=50,
        nse_cliente_objetivo=["B", "A/B"],
        importancia_afluencia=1.2,
        importancia_competencia=1.0,
    )

    PRESUPUESTO_PORTAFOLIO = 50000.0

    print(f"=== GDL NEXUS - Optimización de Portafolio Voraz ===")
    print(f"Presupuesto Global Disponible: ${PRESUPUESTO_PORTAFOLIO:,.2f}/mes\n")

    resultado_portafolio = construir_portafolio_voraz(perfil_usuario, datos_zonas, PRESUPUESTO_PORTAFOLIO)

    print("Zonas Seleccionadas para Expansión:")
    print(f"{'#':<3} {'Zona':<25} {'Score':>7} {'Costo Renta':>15} {'Alertas'}")
    print("-" * 75)
    for idx, z in enumerate(resultado_portafolio.zonas_seleccionadas, 1):
        print(f"{idx:<3} {z.zona_nombre:<25} {z.score_total:>6.1f}%   ${z.renta_estimada:>13,.2f}  {len(z.alertas)} alertas")

    print("-" * 75)
    print(f"Resumen Financiero del Portafolio:")
    print(f" Total Invertido:  ${resultado_portafolio.presupuesto_utilizado:,.2f}")
    print(f" Total Remanente:  ${resultado_portafolio.presupuesto_remanente:,.2f}")
    print(f" Score Total Acumulado: {resultado_portafolio.score_acumulado_total:.2f} pts")
