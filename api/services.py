"""Lógica para las operaciones de simulación."""

import os
import shutil
import sys
import uuid
from datetime import datetime, timezone, timedelta
from typing import List

import numpy as np

# Para generar el gráfico igual pero sin display ya que Docker es headless
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import scipy.io as sio

from .schemas import SimulationParams, SimulationResult, EFRResult

# Configurar rutas para el modelo Verhulst
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..'))
MODEL_DIR = os.path.join(REPO_ROOT, 'Verhulstetal2018Model')
sys.path.insert(0, MODEL_DIR)

from get_RAM_stims import get_RAM_stims
from model2018 import model2018

# Constantes
POLES_BASE = os.path.join(REPO_ROOT, 'Verhulstetal2018Model', 'Poles')
FUNDAMENTAL_HZ = 110
NUM_HARMONICS = 4
# Al estar dentro de Docker, usará UTC por defecto -> se fuerza UTC-3 por el momento
TZ_AR = timezone(timedelta(hours=-3))


def load_poles(profile: str) -> np.ndarray:
    """Carga la configuración de poles desde archivo."""
    path = os.path.join(POLES_BASE, profile, 'StartingPoles.dat')
    if not os.path.exists(path):
        available = list_poles()
        raise FileNotFoundError(
            f"Perfil '{profile}' no encontrado en {POLES_BASE}/. "
            f"Disponibles: {available}"
        )
    poles = np.loadtxt(path)
    if poles.ndim > 1:
        poles = poles[0, :]
    return poles


def list_poles() -> List[str]:
    """Lista los perfiles auditivos disponibles."""
    if not os.path.isdir(POLES_BASE):
        return []
    return sorted(
        d for d in os.listdir(POLES_BASE)
        if os.path.isdir(os.path.join(POLES_BASE, d))
    )


def calculate_efr(output) -> tuple[EFRResult, np.ndarray, np.ndarray, np.ndarray]:
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


def run_simulation(params: SimulationParams) -> SimulationResult:
    """Corre una simulación completa y devuelve el resultado."""
    sim_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now(TZ_AR).strftime('%Y-%m-%dT%H-%M-%S')
    folder_name = f"{timestamp}_{sim_id}"
    sim_dir = os.path.join(REPO_ROOT, 'simulations_results', folder_name)

    print(f"[{sim_id} - INFO] Iniciando simulación — carrier={params.carrier_freq}Hz, perfil={params.poles_profile}")
    os.makedirs(sim_dir, exist_ok=True)
    print(f"[{sim_id} - INFO] Directorio creado: {sim_dir}")

    try:
        poles = load_poles(params.poles_profile)
        print(f"[{sim_id} - INFO] Poles cargados ({len(poles)} valores)")
    except FileNotFoundError as e:
        shutil.rmtree(sim_dir, ignore_errors=True)
        print(f"[{sim_id} - ERROR] Perfil no encontrado: {e}")
        return SimulationResult(
            status='error',
            carrier_freq=params.carrier_freq,
            poles_profile=params.poles_profile,
            sim_id=None,
            error=str(e),
        )

    try:
        stimulus = get_RAM_stims(params.fs, np.array([params.carrier_freq]))
        print(f"[{sim_id} - INFO] Estímulo generado — {stimulus.shape[1]} samples ({stimulus.shape[1]/params.fs:.3f}s)")

        storeflag = params.storeflag
        if 'w' not in storeflag:
            storeflag += 'w'
        if 'b' not in storeflag:
            storeflag += 'b'
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
        efr, f_axis, P1, EFR_combined = calculate_efr(output)
        print(f"[{sim_id} - INFO] EFR calculado: {efr.efr_value_uV:.4f} µV")

        sio.savemat(os.path.join(sim_dir, 'efr.mat'), {
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

        if params.save_raw:
            np.savez(os.path.join(sim_dir, 'raw.npz'),
                cf=output.cf,
                stimulus=stimulus,
                fs_bm=output.fs_bm,
            )
            print(f"[{sim_id} - INFO] raw.npz guardado")
            if 'v' in storeflag:
                np.savez(os.path.join(sim_dir, 'bm_velocity.npz'),
                    v=output.v,
                )
                print(f"[{sim_id} - INFO] bm_velocity.npz guardado")

        fs_an = float(output.fs_an)
        t_efr = np.arange(len(EFR_combined.flatten())) / fs_an
        t_stim = np.arange(stimulus.shape[1]) / params.fs

        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        fig.suptitle(
            f'Simulación — Carrier: {params.carrier_freq} Hz | Perfil: {params.poles_profile}',
            fontsize=14,
        )

        axes[0, 0].plot(t_stim[:1000], stimulus[0][:1000])
        axes[0, 0].set_title('Estímulo RAM (primeros 10 ms)')
        axes[0, 0].set_xlabel('Tiempo (s)')
        axes[0, 0].set_ylabel('Amplitud')
        axes[0, 0].grid(True)

        axes[0, 1].plot(t_efr, EFR_combined.flatten())
        axes[0, 1].set_title('Forma de onda EFR (w1+w3+w5)')
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

        axes[1, 1].plot(t_efr, output.w1.flatten(), label='Onda 1', alpha=0.7)
        axes[1, 1].plot(t_efr, output.w3.flatten(), label='Onda 3', alpha=0.7)
        axes[1, 1].plot(t_efr, output.w5.flatten(), label='Onda 5', alpha=0.7)
        axes[1, 1].set_title('Ondas ABR individuales')
        axes[1, 1].set_xlabel('Tiempo (s)')
        axes[1, 1].set_ylabel('Amplitud')
        axes[1, 1].legend()
        axes[1, 1].grid(True)

        plt.tight_layout()
        plt.savefig(os.path.join(sim_dir, 'plot.png'), dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"[{sim_id} - INFO] plot.png guardado")

        print(f"[{sim_id} - INFO] Simulación completada OK")
        return SimulationResult(
            status='ok',
            carrier_freq=params.carrier_freq,
            poles_profile=params.poles_profile,
            sim_id=sim_id,
            efr=efr,
        )

    except Exception as e:
        shutil.rmtree(sim_dir, ignore_errors=True)
        print(f"[{sim_id} - ERROR] {type(e).__name__}: {e}")
        return SimulationResult(
            status='error',
            carrier_freq=params.carrier_freq,
            poles_profile=params.poles_profile,
            sim_id=None,
            error=str(e),
        )
