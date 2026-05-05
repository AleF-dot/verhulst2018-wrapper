"""API route handlers for simulation endpoints."""

import concurrent.futures
from typing import List

from fastapi import APIRouter, HTTPException

from .schemas import BatchSimulationRequest, SimulationParams, SimulationResult
from .services import list_poles, run_simulation

POLES_BASE_MSG = "No se encontraron perfiles en Poles/. Verificá que Poles.zip fue descomprimido."

router = APIRouter()


@router.get('/health')
def health():
    return {'status': 'ok', 'model': 'Verhulst 2018'}


@router.get('/poles', response_model=List[str])
def get_poles():
    """Get available auditory profiles."""
    profiles = list_poles()
    if not profiles:
        raise HTTPException(
            status_code=404,
            detail=POLES_BASE_MSG,
        )
    return profiles


@router.post('/simulate', response_model=SimulationResult)
def simulate(params: SimulationParams):
    """Run a single simulation with given parameters."""
    return run_simulation(params)


@router.post('/simulate/batch', response_model=List[SimulationResult])
def simulate_batch(request: BatchSimulationRequest):
    """Run multiple simulations in parallel."""
    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = list(executor.map(run_simulation, request.simulations))
    return results