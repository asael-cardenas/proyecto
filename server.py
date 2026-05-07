"""
GDL Nexus - Backend API
Sprint 1 → HU01  · Sprint 2 → HU02  · Sprint 3 → HU03 + HU04

Uso:
    cd backend
    uvicorn server:app --reload --port 8000
    → Abre http://localhost:8000
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend import (
    InputUsuario, cargar_datos_zonas,
    evaluar_factibilidad_FB, resultado_a_dict,
)
from visibilidad import rankear_zonas_por_visibilidad, visibilidad_a_dict
from comparacion import (
    filtrar_zonas_por_giro, filtro_giro_a_dict,
    comparar_zonas, comparacion_a_dict,
)

app = FastAPI(title="GDL Nexus API", version="3.0.0-sprint3")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH    = os.path.join(BASE_DIR,"proyecto","zonas_zmg.json")
FRONTEND_DIR = os.path.join(BASE_DIR,"proyecto")


@app.get("/", include_in_schema=False)
def serve_ui():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# ── MODELOS ───────────────────────────────────────────────────────────────────

class AnalisisRequest(BaseModel):
    giro: str                          = Field(..., example="cafeteria")
    presupuesto_renta_mensual: float   = Field(..., gt=0, example=18000)
    metros_cuadrados_requeridos: float = Field(..., gt=0, example=50)
    nse_cliente_objetivo: list[str]    = Field(..., example=["B", "A/B"])
    importancia_afluencia: float       = Field(1.0, ge=0.5, le=1.5)
    importancia_precio: float          = Field(1.0, ge=0.5, le=1.5)
    importancia_competencia: float     = Field(1.0, ge=0.5, le=1.5)

class ComparacionRequest(BaseModel):
    zona_ids: list[str]                = Field(..., min_length=2, max_length=4)
    giro: str                          = Field(..., example="cafeteria")
    presupuesto_renta_mensual: float   = Field(..., gt=0, example=18000)
    metros_cuadrados_requeridos: float = Field(..., gt=0, example=50)
    nse_cliente_objetivo: list[str]    = Field(..., example=["B", "A/B"])
    importancia_afluencia: float       = Field(1.0, ge=0.5, le=1.5)
    importancia_precio: float          = Field(1.0, ge=0.5, le=1.5)
    importancia_competencia: float     = Field(1.0, ge=0.5, le=1.5)


def _datos():
    try:
        return cargar_datos_zonas(DATA_PATH)
    except FileNotFoundError:
        raise HTTPException(500, "Base de datos no encontrada.")

def _val_giro(giro, datos):
    if giro not in datos.get("giros_disponibles", []):
        raise HTTPException(400, f"Giro '{giro}' no válido.")

def _val_nse(nse_list, datos):
    validos = list(datos.get("nse_rangos", {}).keys())
    for n in nse_list:
        if n not in validos:
            raise HTTPException(400, f"NSE '{n}' no válido.")


# ── SPRINT 1 — HU01 ──────────────────────────────────────────────────────────

@app.get("/zonas")
def listar_zonas():
    datos = _datos()
    return {"total": len(datos["zonas"]), "zonas": [
        {"id": z["id"], "nombre": z["nombre"], "lat": z["lat"], "lng": z["lng"],
         "nse": z["nse"], "renta_m2": z["renta_m2"], "descripcion": z["descripcion"]}
        for z in datos["zonas"]
    ]}

@app.get("/giros")
def listar_giros():
    return {"giros": _datos().get("giros_disponibles", [])}

@app.post("/analizar")
def analizar_factibilidad(req: AnalisisRequest):
    """HU01 — Factibilidad brute-force en todas las zonas."""
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
    rs = [resultado_a_dict(r) for r in evaluar_factibilidad_FB(usuario, datos)]
    return {
        "input": {"giro": req.giro, "presupuesto": req.presupuesto_renta_mensual,
                  "metros": req.metros_cuadrados_requeridos, "nse_objetivo": req.nse_cliente_objetivo},
        "total_zonas_analizadas": len(rs),
        "top_3_recomendadas": rs[:3],
        "analisis_completo": rs,
        "resumen": {
            "zonas_verdes":    sum(1 for r in rs if r["semaforo"] == "VERDE"),
            "zonas_amarillas": sum(1 for r in rs if r["semaforo"] == "AMARILLO"),
            "zonas_rojas":     sum(1 for r in rs if r["semaforo"] == "ROJO"),
        },
    }

@app.get("/zona/{zona_id}")
def detalle_zona(zona_id: str):
    datos = _datos()
    zona = next((z for z in datos["zonas"] if z["id"] == zona_id), None)
    if not zona:
        raise HTTPException(404, f"Zona '{zona_id}' no encontrada.")
    return zona


# ── SPRINT 2 — HU02 ──────────────────────────────────────────────────────────

@app.get("/visibilidad/{giro}")
def ranking_visibilidad(giro: str):
    """HU02 — Ranking de zonas por visibilidad comercial para un giro."""
    datos = _datos()
    _val_giro(giro, datos)
    rs = [visibilidad_a_dict(r) for r in rankear_zonas_por_visibilidad(giro, datos)]
    return {"giro": giro, "total": len(rs), "ranking": rs, "top_zona": rs[0] if rs else None}


# ── SPRINT 3 — HU03 ──────────────────────────────────────────────────────────

@app.get("/filtro-giro/{giro}")
def filtro_por_giro(giro: str):
    """HU03 — Zonas recomendadas para un giro: evalúa saturación y complementariedad."""
    datos = _datos()
    _val_giro(giro, datos)
    rs = [filtro_giro_a_dict(r) for r in filtrar_zonas_por_giro(giro, datos)]
    return {
        "giro": giro,
        "total_zonas": len(rs),
        "zonas_aptas": sum(1 for r in rs if r["apto"]),
        "zonas_no_aptas": sum(1 for r in rs if not r["apto"]),
        "ranking": rs,
    }


# ── SPRINT 3 — HU04 ──────────────────────────────────────────────────────────

@app.post("/comparar")
def comparar(req: ComparacionRequest):
    """HU04 — Comparación lado a lado de 2–4 zonas seleccionadas."""
    datos = _datos()
    _val_giro(req.giro, datos)
    _val_nse(req.nse_cliente_objetivo, datos)
    ids_validos = {z["id"] for z in datos["zonas"]}
    for zid in req.zona_ids:
        if zid not in ids_validos:
            raise HTTPException(400, f"zona_id '{zid}' no existe.")

    usuario = InputUsuario(
        giro=req.giro,
        presupuesto_renta_mensual=req.presupuesto_renta_mensual,
        metros_cuadrados_requeridos=req.metros_cuadrados_requeridos,
        nse_cliente_objetivo=req.nse_cliente_objetivo,
        importancia_afluencia=req.importancia_afluencia,
        importancia_precio=req.importancia_precio,
        importancia_competencia=req.importancia_competencia,
    )
    fichas = [comparacion_a_dict(f) for f in comparar_zonas(req.zona_ids, usuario, datos)]
    ganadores = {}
    if fichas:
        ganadores = {
            "mejor_factibilidad": max(fichas, key=lambda f: f["scores"]["factibilidad"])["zona_nombre"],
            "mejor_visibilidad":  max(fichas, key=lambda f: f["scores"]["visibilidad"])["zona_nombre"],
            "mejor_aptitud_giro": max(fichas, key=lambda f: f["scores"]["aptitud_giro"])["zona_nombre"],
        }
    return {"zonas_comparadas": len(fichas), "fichas": fichas, "ganadores": ganadores}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
