"""
GDL Nexus — API REST
Versión unificada: un único endpoint combina factibilidad,
visibilidad, aptitud de giro y posición relativa.

Uso:
    cd backend
    uvicorn server:app --reload --port 8000
"""

import os, gzip, base64
import json as _json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Literal

from algoritmo_factibilidad import InputUsuario, cargar_datos_zonas
from analisis_unificado import evaluar_unificado, unificado_a_dict

app = FastAPI(title="GDL Nexus API", version="5.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH    = os.path.join(BASE_DIR, "proyecto",     "zonas_zmg.json")
FRONTEND_DIR = os.path.join(BASE_DIR, "proyecto")

@app.get("/", include_in_schema=False)
def serve_ui():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

def _datos():
    try:    return cargar_datos_zonas(DATA_PATH)
    except FileNotFoundError: raise HTTPException(500, "Base de datos no encontrada.")

def _val_giro(giro, datos):
    if giro not in datos.get("giros_disponibles", []):
        raise HTTPException(400, f"Giro '{giro}' no válido.")

def _val_nse(nse_list, datos):
    validos = list(datos.get("nse_rangos", {}).keys())
    for n in nse_list:
        if n not in validos:
            raise HTTPException(400, f"NSE '{n}' no válido.")

def _comprimir_log(log) -> dict:
    pasos_json = _json.dumps(log.pasos, ensure_ascii=False).encode("utf-8")
    pasos_gz   = gzip.compress(pasos_json, compresslevel=9)
    pasos_b64  = base64.b64encode(pasos_gz).decode("ascii")
    return {
        "algoritmo":                log.algoritmo,
        "zonas_total":              log.zonas_total,
        "zonas_evaluadas_completo": log.zonas_evaluadas_completo,
        "zonas_podadas":            log.zonas_podadas,
        "pasos_encoding":           "gzip+base64",
        "pasos_raw_bytes":          len(pasos_json),
        "pasos_gz_bytes":           len(pasos_gz),
        "pasos":                    pasos_b64,
    }


class AnalisisRequest(BaseModel):
    giro:                        str       = Field(...,  example="cafeteria")
    presupuesto_renta_mensual:   float     = Field(...,  gt=0,  example=18000)
    metros_cuadrados_requeridos: float     = Field(...,  gt=0,  example=50)
    nse_cliente_objetivo:        list[str] = Field(...,  example=["B", "A/B"])
    importancia_afluencia:       float     = Field(1.0,  ge=0.5, le=1.5)
    importancia_precio:          float     = Field(1.0,  ge=0.5, le=1.5)
    importancia_competencia:     float     = Field(1.0,  ge=0.5, le=1.5)
    peso_factibilidad:           float     = Field(1.0,  ge=0.5, le=1.5)
    peso_visibilidad:            float     = Field(1.0,  ge=0.5, le=1.5)
    peso_aptitud_giro:           float     = Field(1.0,  ge=0.5, le=1.5)
    peso_posicion_rel:           float     = Field(1.0,  ge=0.5, le=1.5)
    algoritmo: Literal["brute_force","greedy","divide_y_venceras"] = "brute_force"


@app.get("/zonas")
def listar_zonas():
    datos = _datos()
    return {"total": len(datos["zonas"]), "zonas": [
        {"id": z["id"], "nombre": z["nombre"], "lat": z["lat"], "lng": z["lng"],
         "nse": z["nse"], "renta_m2": z["renta_m2"], "descripcion": z["descripcion"]}
        for z in datos["zonas"]]}

@app.get("/giros")
def listar_giros():
    return {"giros": _datos().get("giros_disponibles", [])}

@app.get("/zona/{zona_id}")
def detalle_zona(zona_id: str):
    datos = _datos()
    zona  = next((z for z in datos["zonas"] if z["id"] == zona_id), None)
    if not zona: raise HTTPException(404, f"Zona '{zona_id}' no encontrada.")
    return zona

@app.post("/analizar")
def analizar(req: AnalisisRequest):
    """
    Análisis unificado: evalúa todas las zonas combinando
    factibilidad (40%), visibilidad (25%), aptitud de giro (20%)
    y posición relativa (15%) en un único score por zona.
    """
    datos = _datos()
    _val_giro(req.giro, datos)
    _val_nse(req.nse_cliente_objetivo, datos)

    usuario = InputUsuario(
        giro=req.giro,
        presupuesto_renta_mensual=req.presupuesto_renta_mensual,
        metros_cuadrados_requeridos=req.metros_cuadrados_requeridos,
        nse_cliente_objetivo=req.nse_cliente_objetivo,
        importancia_afluencia=req.importancia_afluencia,
        importancia_precio=req.importancia_precio,
        importancia_competencia=req.importancia_competencia,
    )

    resultados, log_obj = evaluar_unificado(
        usuario=usuario, datos=datos,
        peso_factibilidad=req.peso_factibilidad,
        peso_visibilidad=req.peso_visibilidad,
        peso_aptitud_giro=req.peso_aptitud_giro,
        peso_posicion_rel=req.peso_posicion_rel,
        algoritmo=req.algoritmo,
    )

    rs = [unificado_a_dict(r) for r in resultados]
    return {
        "algoritmo_usado": req.algoritmo,
        "input": {"giro": req.giro, "presupuesto": req.presupuesto_renta_mensual,
                  "metros": req.metros_cuadrados_requeridos,
                  "nse_objetivo": req.nse_cliente_objetivo},
        "total_zonas_analizadas": len(rs),
        "analisis_completo": rs,
        "resumen": {
            "zonas_verdes":    sum(1 for r in rs if r["semaforo"] == "VERDE"),
            "zonas_amarillas": sum(1 for r in rs if r["semaforo"] == "AMARILLO"),
            "zonas_rojas":     sum(1 for r in rs if r["semaforo"] == "ROJO"),
        },
        "log": _comprimir_log(log_obj) if log_obj else None,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
