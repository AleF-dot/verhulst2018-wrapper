"""API principal — punto de entrada FastAPI para el modelo Verhulst 2018."""

import logging
import os
import shutil
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router

RESULTS_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulations_results'))
logger = logging.getLogger(__name__)


def cleanup_orphaned():
    results_path = Path(RESULTS_DIR)
    if not results_path.exists():
        return
    for folder in results_path.iterdir():
        if folder.is_dir() and not (folder / 'efr.mat').exists():
            shutil.rmtree(folder)
            logger.warning(f'Carpeta huérfana eliminada: {folder.name}')

@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_orphaned()
    yield

app = FastAPI(
    title='Verhulst 2018 Simulation API',
    description='API para correr simulaciones del modelo de periferia auditiva Verhulst 2018.',
    version='0.1.0',
    lifespan=lifespan,
)

# CORS activado unicamente en contexto de desarrollo
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(router)