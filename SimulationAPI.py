"""
SimulationAPI.py
FastAPI wrapper sobre el modelo Verhulst 2018.

Endpoints:
    GET  /health          — estado del servidor
    GET  /poles           — lista de perfiles disponibles
    POST /simulate        — corre una simulación con parámetros configurables
    POST /simulate/batch  — corre N simulaciones en paralelo
"""

import os
import shutil
import numpy as np
import concurrent.futures
from typing import Optional, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from get_RAM_stims import get_RAM_stims
from model2018 import model2018

# CORS!
from fastapi.middleware.cors import CORSMiddleware

# Para generar el gráfico igual pero sin display ya que Docker es headless
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import uuid
import scipy.io as sio

# Al estar dentro de Docker, usará UTC por defecto -> se fuerza UTC-3 por el momento
from datetime import datetime, timezone, timedelta
TZ_AR = timezone(timedelta(hours=-3))

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

# Hardcodeadas igual que en el modelo original (No es configurable sin cambiar el estímulo.)
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
            "Forzado internamente: 'w'. Máximo: 'evihmlbw'."
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

    # Guardado de arrays crudos
    save_raw: bool = Field(
    default=False,
    description=(
        "Si es True, guarda raw.npz (cf, stimulus, fs_bm) y, si 'v' está en storeflag, "
        "también bm_velocity.npz con la velocidad de la membrana basilar."
    )
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
    sim_id: Optional[str] = None
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


def _calculate_efr(output) -> tuple[EFRResult, np.ndarray, np.ndarray, np.ndarray]:
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
    ), f, P1, EFR

def _run_single(params: SimulationParams) -> SimulationResult:
    """Corre una simulación completa y devuelve el resultado."""
    sim_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now(TZ_AR).strftime("%Y-%m-%dT%H-%M-%S")
    folder_name = f"{timestamp}_{sim_id}"
    sim_dir = f"/app/simulations_results/{folder_name}"

    print(f"[{sim_id} - INFO] Iniciando simulación — carrier={params.carrier_freq}Hz, profile={params.poles_profile}")
    os.makedirs(sim_dir, exist_ok=True)
    print(f"[{sim_id} - INFO] Directorio creado: {sim_dir}")

    try:
        poles = _load_poles(params.poles_profile)
        print(f"[{sim_id} - INFO] Poles cargados ({len(poles)} valores)")
    except FileNotFoundError as e:
        shutil.rmtree(sim_dir, ignore_errors=True)
        print(f"[{sim_id} - ERROR] Perfil no encontrado: {e}")
        return SimulationResult(
            status="error",
            carrier_freq=params.carrier_freq,
            poles_profile=params.poles_profile,
            sim_id=None,
            error=str(e),
        )

    try:
        stimulus = get_RAM_stims(params.fs, np.array([params.carrier_freq]))
        print(f"[{sim_id} - INFO] Estímulo generado — {stimulus.shape[1]} samples ({stimulus.shape[1]/params.fs:.3f}s)")

        storeflag = params.storeflag
        if "w" not in storeflag:
            storeflag += "w"
        if "b" not in storeflag:
            storeflag += "b"
        # 'w' en storeflag dispara anfM y anfL pero NO anfH (bug en model2018.py línea 251:
        # le falta 'or w in storeflag' en la condición). Se fuerza 'b' como workaround
        # hasta que el modelo sea corregido o se haga un patch local (no óptimo).
        print(f"[{sim_id} - INFO] Storeflag efectivo: '{storeflag}'")

        print(f"[{sim_id} - INFO] Corriendo modelo...")
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
            data_folder=sim_dir,
        )
        print(f"[{sim_id} - INFO] Modelo completado")

        output = results[0]
        # Evita recalcular efr
        efr, f_axis, P1, EFR_combined = _calculate_efr(output)
        print(f"[{sim_id} - INFO] EFR calculado: {efr.efr_value_uV:.4f} µV")
        
        # Guardar EFR y ondas ABR
        sio.savemat(f"{sim_dir}/efr.mat", {
            'EFR': EFR_combined,
            'w1': output.w1,
            'w3': output.w3,
            'w5': output.w5,
            'efr_value_uV': efr.efr_value_uV,
            'fs': output.fs_an,
            'carrier_freq': params.carrier_freq,
            'poles_profile': params.poles_profile,
        })
        print(f"[{sim_id} - INFO] efr.mat guardado")

        # Guardar arrays crudos si se especificó
        if params.save_raw:
            # cf, stimulus y fs_bm siempre disponibles
            np.savez(f"{sim_dir}/raw.npz",
                cf=output.cf,
                stimulus=stimulus,
                fs_bm=output.fs_bm,
            )
            print(f"[{sim_id} - INFO] raw.npz guardado")
            # v (velocidad BM) solo disponible si 'v' estaba en storeflag
            if 'v' in storeflag:
                np.savez(f"{sim_dir}/bm_velocity.npz",
                    v=output.v,
                )
                print(f"[{sim_id} - INFO] bm_velocity.npz guardado")

        # Generar y guardar gráfico (WIP)
        fs_an = float(output.fs_an)
        t_efr = np.arange(len(EFR_combined.flatten())) / fs_an
        t_stim = np.arange(stimulus.shape[1]) / params.fs

        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        fig.suptitle(
            f'Simulación — Carrier: {params.carrier_freq} Hz | Perfil: {params.poles_profile}',
            fontsize=14
        )

        axes[0, 0].plot(t_stim[:1000], stimulus[0][:1000])
        axes[0, 0].set_title('Estímulo RAM (primeros 10 ms)')
        axes[0, 0].set_xlabel('Tiempo (s)')
        axes[0, 0].set_ylabel('Amplitud')
        axes[0, 0].grid(True)

        axes[0, 1].plot(t_efr, EFR_combined.flatten())
        axes[0, 1].set_title('Waveform EFR (w1+w3+w5)')
        axes[0, 1].set_xlabel('Tiempo (s)')
        axes[0, 1].set_ylabel('Amplitud')
        axes[0, 1].grid(True)

        axes[1, 0].semilogy(f_axis, P1)
        for h in [FUNDAMENTAL_HZ * k for k in range(1, NUM_HARMONICS + 1)]:
            idx = int(np.argmin(np.abs(f_axis - h)))
            axes[1, 0].semilogy(f_axis[idx], P1[idx], 'ro', markersize=8, label=f'{h} Hz')
        axes[1, 0].set_title('Espectro FFT con armónicos')
        axes[1, 0].set_xlabel('Frecuencia (Hz)')
        axes[1, 0].set_ylabel('Potencia')
        axes[1, 0].set_xlim(0, 500)
        axes[1, 0].legend()
        axes[1, 0].grid(True)

        axes[1, 1].plot(t_efr, output.w1.flatten(), label='Wave 1', alpha=0.7)
        axes[1, 1].plot(t_efr, output.w3.flatten(), label='Wave 3', alpha=0.7)
        axes[1, 1].plot(t_efr, output.w5.flatten(), label='Wave 5', alpha=0.7)
        axes[1, 1].set_title('Ondas ABR individuales')
        axes[1, 1].set_xlabel('Tiempo (s)')
        axes[1, 1].set_ylabel('Amplitud')
        axes[1, 1].legend()
        axes[1, 1].grid(True)

        plt.tight_layout()
        plt.savefig(f"{sim_dir}/plot.png", dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"[{sim_id} - INFO] plot.png guardado")

        print(f"[{sim_id} - INFO] Simulación completada OK")
        return SimulationResult(
            status="ok",
            carrier_freq=params.carrier_freq,
            poles_profile=params.poles_profile,
            sim_id=sim_id,
            efr=efr,
        )

    except Exception as e:
        shutil.rmtree(sim_dir, ignore_errors=True)
        print(f"[{sim_id} - ERROR] {type(e).__name__}: {e}")
        return SimulationResult(
            status="error",
            carrier_freq=params.carrier_freq,
            poles_profile=params.poles_profile,
            sim_id=None,
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


@app.post("/simulate/batch", response_model=List[SimulationResult])
def simulate_batch(request: BatchSimulationRequest):
    """
    Corre N simulaciones en paralelo (ProcessPoolExecutor, un proceso por simulación).
    El orden de los resultados corresponde al orden de entrada.
    """
    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = list(executor.map(_run_single, request.simulations))
    return results