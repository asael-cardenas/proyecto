import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend import (
    InputUsuario,
    cargar_datos_zonas,
    evaluar_factibilidad_FB,
    resultado_a_dict,
)

app = FastAPI(
    title="GDL Nexus API",
    description="Business Intelligence para emprendedores de la ZMG",
    version="1.0.0-sprint1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH    = os.path.join("zonas_zmg.json")
FRONTEND_DIR = os.path.join(BASE_DIR, "algoritmos")

@app.get("/", include_in_schema=False)
def serve_ui():
    return FileResponse(os.path.join("index.html"))


class AnalisisRequest(BaseModel):
    giro: str                          = Field(...,  example="cafeteria")
    presupuesto_renta_mensual: float   = Field(...,  gt=0,  example=18000)
    metros_cuadrados_requeridos: float = Field(...,  gt=0,  example=50)
    nse_cliente_objetivo: list[str]    = Field(...,  example=["B", "A/B"])
    importancia_afluencia: float       = Field(1.0,  ge=0.5, le=1.5)
    importancia_precio: float          = Field(1.0,  ge=0.5, le=1.5)
    importancia_competencia: float     = Field(1.0,  ge=0.5, le=1.5)


@app.get("/zonas")
def listar_zonas():
    datos = cargar_datos_zonas(DATA_PATH)
    return {
        "total": len(datos["zonas"]),
        "zonas": [
            {
                "id":          z["id"],
                "nombre":      z["nombre"],
                "lat":         z["lat"],
                "lng":         z["lng"],
                "nse":         z["nse"],
                "renta_m2":    z["renta_m2"],
                "descripcion": z["descripcion"],
            }
            for z in datos["zonas"]
        ],
    }


@app.get("/giros")
def listar_giros():
    datos = cargar_datos_zonas(DATA_PATH)
    return {"giros": datos["giros_disponibles"]}


@app.post("/analizar")
def analizar_factibilidad(request: AnalisisRequest):
    try:
        datos = cargar_datos_zonas(DATA_PATH)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Base de datos de zonas no encontrada.")

    # Validar giro
    giros_validos = datos.get("giros_disponibles", [])
    if request.giro not in giros_validos:
        raise HTTPException(
            status_code=400,
            detail=f"Giro '{request.giro}' no válido. Opciones: {giros_validos}",
        )

    # Validar NSE
    nse_validos = list(datos.get("nse_rangos", {}).keys())
    for nse in request.nse_cliente_objetivo:
        if nse not in nse_validos:
            raise HTTPException(
                status_code=400,
                detail=f"NSE '{nse}' no válido. Opciones: {nse_validos}",
            )

    usuario = InputUsuario(
        giro=request.giro,
        presupuesto_renta_mensual=request.presupuesto_renta_mensual,
        metros_cuadrados_requeridos=request.metros_cuadrados_requeridos,
        nse_cliente_objetivo=request.nse_cliente_objetivo,
        importancia_afluencia=request.importancia_afluencia,
        importancia_precio=request.importancia_precio,
        importancia_competencia=request.importancia_competencia,
    )

    resultados      = evaluar_factibilidad_FB(usuario, datos)
    resultados_dict = [resultado_a_dict(r) for r in resultados]

    return {
        "input": {
            "giro":         request.giro,
            "presupuesto":  request.presupuesto_renta_mensual,
            "metros":       request.metros_cuadrados_requeridos,
            "nse_objetivo": request.nse_cliente_objetivo,
        },
        "total_zonas_analizadas": len(resultados_dict),
        "top_3_recomendadas":     resultados_dict[:3],
        "analisis_completo":      resultados_dict,
        "resumen": {
            "zonas_verdes":    sum(1 for r in resultados_dict if r["semaforo"] == "VERDE"),
            "zonas_amarillas": sum(1 for r in resultados_dict if r["semaforo"] == "AMARILLO"),
            "zonas_rojas":     sum(1 for r in resultados_dict if r["semaforo"] == "ROJO"),
        },
    }


@app.get("/zona/{zona_id}")
def detalle_zona(zona_id: str):
    """Retorna los datos completos de una zona específica."""
    datos = cargar_datos_zonas(DATA_PATH)
    zona  = next((z for z in datos["zonas"] if z["id"] == zona_id), None)
    if not zona:
        raise HTTPException(status_code=404, detail=f"Zona '{zona_id}' no encontrada.")
    return zona


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
