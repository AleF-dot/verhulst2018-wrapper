"""Definición de rutas de la API."""

import logging
import os
import time
import concurrent.futures
from typing import List

from fastapi import APIRouter, HTTPException

from .schemas import BatchSimulationRequest, SimulationParams, SimulationResult
from .services import list_poles, run_simulation

MAX_WORKERS = int(os.getenv('MAX_WORKERS', '2'))
POLES_BASE_MSG = "No se encontraron perfiles en Poles/. Verificá que Poles.zip fue descomprimido."

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get('/health')
def health():
    return {'status': 'ok', 'model': 'Verhulst 2018'}


@router.get('/poles', response_model=List[str])
def get_poles():
    """Lista los perfiles auditivos disponibles en Poles/."""
    profiles = list_poles()
    if not profiles:
        raise HTTPException(
            status_code=404,
            detail=POLES_BASE_MSG,
        )
    return profiles


@router.post('/simulate', response_model=SimulationResult)
def simulate(params: SimulationParams):
    """Corre una simulación individual con los parámetros dados."""
    return run_simulation(params)


@router.post('/simulate/batch', response_model=List[SimulationResult])
def simulate_batch(request: BatchSimulationRequest):
    """Corre múltiples simulaciones en paralelo."""
    logger.info(f"Batch recibido — {len(request.simulations)} simulaciones | MAX_WORKERS={MAX_WORKERS}")
    _t0 = time.perf_counter()
    with concurrent.futures.ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(run_simulation, request.simulations))
        logger.info(f"Batch completado — {time.perf_counter()-_t0:.2f}s | {len(results)} resultados")
    return results