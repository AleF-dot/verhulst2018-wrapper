"""
API principal para el modelo Verhulst 2018.

Este archivo es el punto de entrada de la aplicación FastAPI.
La lógica se ha refactorizado desde el monolito original SimulationAPI.py
en los siguientes módulos:

- api/routes.py       -> Definición de los endpoints (/health, /poles, /simulate, /simulate/batch)
- api/schemas.py      -> Modelos Pydantic (SimulationParams, BatchSimulationRequest, SimulationResult, etc.)
- api/services.py     -> Lógica de negocio para cargar poles, correr simulaciones, calcular EFR, etc.
- api/__init__.py      -> Exportación de app y modelos para compatibilidad con SimulationAPI.py

La refactorización busca separar responsabilidades, facilitar pruebas unitarias
y mantener un código más limpio y escalable.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router

app = FastAPI(
    title='Verhulst 2018 Simulation API',
    description='API para correr simulaciones del modelo de periferia auditiva Verhulst 2018.',
    version='0.1.0',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(router)
