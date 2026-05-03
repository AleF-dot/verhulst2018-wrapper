"""
SimulationAPI.py
FastAPI wrapper sobre el modelo Verhulst 2018.

Endpoints:
    GET  /health          — estado del servidor
    GET  /poles           — lista de perfiles disponibles
    POST /simulate        — corre una simulación con parámetros configurables
    POST /simulate/batch  — corre N simulaciones en paralelo (WIP, ¿necesita ParallelRAMSimulationsEFR?)
"""

import os
import sys
import numpy as np
import concurrent.futures
from typing import Optional, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from get_RAM_stims import get_RAM_stims
from model2018 import model2018

# CORS!
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(
    title="Verhulst 2018 Simulation API",
    description="API para correr simulaciones del modelo de periferia auditiva Verhulst 2018.",
    version="0.1.0",
)

# CORS activado SOLO PARA PRODUCCIÓN
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# Rutas base
# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

# SimulationAPI.py vive en /app
# El modelo vive en /app/Verhulstetal2018Model
# Los Poles están en /app/Verhulstetal2018Model/Poles
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POLES_BASE = os.path.join(BASE_DIR, "Verhulstetal2018Model", "Poles")

# Hardcodeadas igual que en el modelo original (Verificar que implica y la posibilidad de editarlo?)
FUNDAMENTAL_HZ = 110
NUM_HARMONICS = 4


# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# Schemas
#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

class SimulationParams(BaseModel):
    """Parámetros de una simulación individual."""

    # Estímulo
    carrier_freq: float = Field(
        default=4000.0,
        description="Frecuencia portadora del estímulo RAM [Hz].",
        gt=0,
    )
    fs: float = Field(
        default=100_000.0,
        description="Frecuencia de muestreo [Hz]. El modelo trabaja internamente a 100kHz.",
        gt=0,
    )

    # Perfil auditivo
    poles_profile: str = Field(
        default="Flat00",
        description=(
            "Nombre de la subcarpeta dentro de Poles/ que contiene el StartingPoles.dat. "
            "Ejemplos: 'Flat00' (audición normal), 'Flat30', 'Flat60', 'Slope30'."
        ),
    )

    # Parámetros del modelo
    fc: str = Field(
        default="abr",
        description=(
            "Secciones de la cóclea a procesar. "
            "'abr' = 401 secciones (recomendado para EFR/ABR), "
            "'half' = 500, 'all' = 1000."
        ),
        pattern="^(abr|half|all)$",
    )
    irregularities: int = Field(
        default=1,
        description="Activar (1) o desactivar (0) irregularidades y no-linealidades cocleares.",
        ge=0, le=1,
    )
    storeflag: str = Field(
        default="w",
        description=(
            "Máscara de variables a guardar. Cada letra activa una salida: "
            "v=velocidad BM, y=desplazamiento BM, e=OAE, i=IHC, "
            "h=fibras HSR, m=fibras MSR, l=fibras LSR, b=CN+IC, w=ondas ABR (w1/w3/w5). "
            "Mínimo recomendado: 'w'. Máximo: 'evihmlbw'."
        ),
    )
    subject: int = Field(
        default=1,
        description="Semilla para las irregularidades aleatorias. Afecta reproducibilidad.",
        ge=1,
    )
    irr_pct: float = Field(
        default=0.05,
        description="Magnitud de perturbaciones aleatorias en la membrana basilar (default 5%).",
        ge=0.0, le=1.0,
    )
    non_linear_type: str = Field(
        default="vel",
        description=(
            "'vel' = no-linealidad instantánea basada en velocidad BM (default). "
            "'none' = modelo lineal."
        ),
        pattern="^(vel|none)$",
    )

    # Fibras del nervio auditivo
    nH: int = Field(
        default=13,
        description="Número de fibras HSR (alta tasa espontánea). Normal = 13.",
        ge=0,
    )
    nM: int = Field(
        default=3,
        description="Número de fibras MSR (media tasa espontánea). Normal = 3.",
        ge=0,
    )
    nL: int = Field(
        default=3,
        description="Número de fibras LSR (baja tasa espontánea). Normal = 3.",
        ge=0,
    )


class BatchSimulationRequest(BaseModel):
    """Múltiples simulaciones a correr en paralelo."""
    simulations: List[SimulationParams] = Field(
        ...,
        description="Lista de configuraciones. Cada una corre en un proceso separado.",
        min_length=1,
        max_length=32,
    )


class EFRResult(BaseModel):
    efr_value_uV: float
    harmonics: dict


class SimulationResult(BaseModel):
    status: str
    carrier_freq: float
    poles_profile: str
    efr: Optional[EFRResult] = None
    error: Optional[str] = None


# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# Helpers
# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

def _load_poles(profile: str) -> np.ndarray:
    path = os.path.join(POLES_BASE, profile, "StartingPoles.dat")
    if not os.path.exists(path):
        available = _list_poles()
        raise FileNotFoundError(
            f"Perfil '{profile}' no encontrado en {POLES_BASE}/. "
            f"Disponibles: {available}"
        )
    poles = np.loadtxt(path)
    if poles.ndim > 1:
        poles = poles[0, :]
    return poles


def _list_poles() -> List[str]:
    if not os.path.isdir(POLES_BASE):
        return []
    return sorted(
        d for d in os.listdir(POLES_BASE)
        if os.path.isdir(os.path.join(POLES_BASE, d))
    )


def _calculate_efr(output) -> EFRResult:
    """Calcula EFR via FFT sobre w1+w3+w5, suma amplitudes en armónicos de 110Hz."""
    fs = float(output.fs_an)
    EFR = output.w1.flatten() + output.w3.flatten() + output.w5.flatten()

    L = len(EFR)
    Y = np.fft.fft(EFR)
    P2 = np.abs(Y / L)
    P1 = P2[: L // 2 + 1]
    P1[1:-1] *= 2
    f = fs * np.arange(L // 2 + 1) / L

    harmonics_hz = [FUNDAMENTAL_HZ * k for k in range(1, NUM_HARMONICS + 1)]
    harmonic_amplitudes = {}
    total = 0.0
    for h in harmonics_hz:
        idx = int(np.argmin(np.abs(f - h)))
        amp = float(P1[idx]) * 1e6
        harmonic_amplitudes[h] = round(amp, 6)
        total += amp

    return EFRResult(
        efr_value_uV=round(total, 6),
        harmonics=harmonic_amplitudes,
    )


def _run_single(params: SimulationParams) -> SimulationResult:
    """Corre una simulación completa y devuelve el resultado."""
    try:
        poles = _load_poles(params.poles_profile)
    except FileNotFoundError as e:
        return SimulationResult(
            status="error",
            carrier_freq=params.carrier_freq,
            poles_profile=params.poles_profile,
            error=str(e),
        )

    try:
        stimulus = get_RAM_stims(params.fs, np.array([params.carrier_freq]))

        # 'w' requiere 'b' (cn/ic/anSummed), y 'b' requiere anfH/anfM/anfL.
        # anfH solo se calcula si hay 'h' o 'b' — 'w' solo NO lo dispara.
        # Por ahora se fuerza ambos para garantizar el pipeline completo hasta EFR.
        # [ IMPORTANTE ] Es necesario revisar el código de los autores en este asunto.
        storeflag = params.storeflag
        if "w" not in storeflag:
            storeflag += "w"
        if "b" not in storeflag:
            storeflag += "b"

        results = model2018(
            stimulus,
            params.fs,
            fc=params.fc,
            irregularities=params.irregularities,
            storeflag=storeflag,
            subject=params.subject,
            sheraPo=poles,
            IrrPct=params.irr_pct,
            non_linear_type=params.non_linear_type,
            nH=params.nH,
            nM=params.nM,
            nL=params.nL,
            clean=1,
            data_folder="./",
        )

        output = results[0]
        efr = _calculate_efr(output)

        return SimulationResult(
            status="ok",
            carrier_freq=params.carrier_freq,
            poles_profile=params.poles_profile,
            efr=efr,
        )

    except Exception as e:
        return SimulationResult(
            status="error",
            carrier_freq=params.carrier_freq,
            poles_profile=params.poles_profile,
            error=str(e),
        )

# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# Endpoints
# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

@app.get("/health")
def health():
    return {"status": "ok", "model": "Verhulst 2018"}


@app.get("/poles", response_model=List[str])
def list_poles():
    """Lista los perfiles auditivos disponibles en Poles/."""
    profiles = _list_poles()
    if not profiles:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontraron perfiles en {POLES_BASE}. "
                    "Verificá que Poles.zip fue descomprimido.",
        )
    return profiles


@app.post("/simulate", response_model=SimulationResult)
def simulate(params: SimulationParams):
    """
    Corre una simulación con los parámetros dados.
    Devuelve EFR en µV con desglose por armónico.
    """
    return _run_single(params)


# [ IMPORTANTE ] Puede que sea necesario crear un identificador (tal vez uuid/hash) para correlacionar los datoss de entrada/salida.

@app.post("/simulate/batch", response_model=List[SimulationResult])
def simulate_batch(request: BatchSimulationRequest):
    """
    Corre N simulaciones en paralelo (ProcessPoolExecutor, un proceso por simulación).
    El orden de los resultados corresponde al orden de entrada.
    """
    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = list(executor.map(_run_single, request.simulations))
    return results