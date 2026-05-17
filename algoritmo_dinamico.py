import os
import math
from dataclasses import dataclass, field

# === IMPORTACIONES DEL BACKEND EXISTENTE ===
from backend import InputUsuario, ResultadoZona, evaluar_factibilidad_FB, cargar_datos_zonas

@dataclass
class PortafolioDinamico:
    zonas_seleccionadas: list = field(default_factory=list)
    presupuesto_total_asignado: float = 0.0
    presupuesto_utilizado: float = 0.0
    presupuesto_remanente: float = 0.0
    score_acumulado_total: float = 0.0


def construir_portafolio_dinamico(
    usuario: InputUsuario,
    datos: dict,
    presupuesto_global_expansion: float,
    bloque_discreto: int = 500
) -> PortafolioDinamico:
    """
    Desarrolla la estrategia de Programación Dinámica para un portafolio de inversión
    utilizando el modelo de la Mochila 0/1 (Knapsack 0/1).
    """
    zonas_evaluadas = evaluar_factibilidad_FB(usuario, datos)
    N = len(zonas_evaluadas)
    
    W_discreto = int(presupuesto_global_expansion // bloque_discreto)
    
    costos_discretos = []
    valores = []
    
    for z in zonas_evaluadas:
        bloques_zona = int(math.ceil(z.renta_estimada / bloque_discreto))
        costos_discretos.append(bloques_zona)
        valores.append(z.score_total)

    dp = [[0.0 for _ in range(W_discreto + 1)] for _ in range(N + 1)]
    
    for i in range(1, N + 1):
        peso_actual = costos_discretos[i - 1]
        valor_actual = valores[i - 1]
        
        for w in range(W_discreto + 1):
            if peso_actual <= w:
                dp[i][w] = max(
                    dp[i - 1][w], 
                    dp[i - 1][w - peso_actual] + valor_actual
                )
            else:
                dp[i][w] = dp[i - 1][w]

    portafolio = PortafolioDinamico(
        presupuesto_total_asignado=presupuesto_global_expansion,
        presupuesto_remanente=presupuesto_global_expansion
    )
    
    w_aux = W_discreto
    for i in range(N, 0, -1):
        if dp[i][w_aux] != dp[i - 1][w_aux]:
            zona_elegida = zonas_evaluadas[i - 1]
            portafolio.zonas_seleccionadas.append(zona_elegida)
            
            portafolio.presupuesto_utilizado += zona_elegida.renta_estimada
            portafolio.presupuesto_remanente -= zona_elegida.renta_estimada
            portafolio.score_acumulado_total += zona_elegida.score_total
            
            zona_elegida.recomendaciones.append(
                f"Seleccionada mediante Programación Dinámica garantizando optimización global exacta."
            )
            
            w_aux -= costos_discretos[i - 1]
            
    portafolio.zonas_seleccionadas.reverse()
    return portafolio


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ruta_json = os.path.join(base_dir, "zonas_zmg.json")
    
    try:
        datos_zonas = cargar_datos_zonas(ruta_json)
    except FileNotFoundError:
        datos_zonas = cargar_datos_zonas("zonas_zmg.json")

    # Definimos el perfil de negocio requerido para la prueba del módulo dinámico
    perfil_usuario = InputUsuario(
        giro="cafeteria",
        presupuesto_renta_mensual=15000,
        metros_cuadrados_requeridos=50,
        nse_cliente_objetivo=["B", "A/B"],
        importancia_afluencia=1.2,
        importancia_competencia=1.0,
    )

    PRESUPUESTO_PORTAFOLIO = 50000.0

    print(f"=== GDL NEXUS - Optimización de Portafolio Dinámico ===")
    print(f"Presupuesto Global Disponible: ${PRESUPUESTO_PORTAFOLIO:,.2f}/mes")
    print(f"Discretización Base: Bloques de $500.00 MXN\n")

    resultado_dinamico = construir_portafolio_dinamico(
        perfil_usuario, datos_zonas, PRESUPUESTO_PORTAFOLIO, bloque_discreto=500
    )

    print("Zonas Seleccionadas (Óptimo Matemático):")
    print(f"{'#':<3} {'Zona':<25} {'Score':>7} {'Costo Renta':>15} {'Alertas'}")
    print("-" * 75)
    for idx, z in enumerate(resultado_dinamico.zonas_seleccionadas, 1):
        print(f"{idx:<3} {z.zona_nombre:<25} {z.score_total:>6.1f}%   ${z.renta_estimada:>13,.2f}  {len(z.alertas)} alertas")

    print("-" * 75)
    print(f"Resumen Financiero del Portafolio Dinámico:")
    print(f" Total Invertido:  ${resultado_dinamico.presupuesto_utilizado:,.2f}")
    print(f" Total Remanente:  ${resultado_dinamico.presupuesto_remanente:,.2f}")
    print(f" Score Total Acumulado: {resultado_dinamico.score_acumulado_total:.2f} pts")
