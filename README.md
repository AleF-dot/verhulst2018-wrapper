# verhulst2018-wrapper

FastAPI wrapper sobre el modelo de periferia auditiva **Verhulst et al. 2018**.
Expone el modelo como API REST containerizada con Docker.

## Requisitos

- [Git](https://git-scm.com/download/win)
- [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install)

## Setup (Windows)

```bat
setup.bat
```

El script clona el modelo original, limpia archivos y levanta el contenedor.

## Setup (Linux / Mac)

```bash
chmod +x setup.sh
./setup.sh
```

El script verifica las dependencias necesarias (`git`, `unzip`, `gcc`, `gfortran`, `docker`) y levanta el contenedor.

## Desarrollo local (sin Docker)

Requiere `gcc` en el PATH para compilar `tridiag.so`.

```bat
run_local_api.bat
```

El script compila `tridiag.so` si no existe, crea el entorno virtual, instala las dependencias y levanta la API con `--reload`.

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Estado del servidor |
| GET | `/poles` | Lista perfiles auditivos disponibles |
| POST | `/simulate` | Corre una simulación |
| POST | `/simulate/batch` | Corre N simulaciones en paralelo |

Documentación interactiva disponible en `http://localhost:8000/docs` una vez levantado el contenedor.

## Resultados

Cada simulación genera una carpeta en `data/simulations/`:

```
2026-05-04T16-17-11_3cd2383d/
├── efr.mat         ← EFR + w1/w3/w5 + metadatos
├── plot.png        ← Gráfico del estímulo, EFR y espectro
├── raw.npz         ← cf, stimulus, fs_bm (si save_raw=true)
└── bm_velocity.npz ← velocidad BM (si save_raw=true y storeflag incluye 'v')
```

## Archivos eliminados del modelo original

Los siguientes archivos de [Verhulstetal2018Model](https://github.com/HearingTechnology/Verhulstetal2018Model) son eliminados por `setup.bat` por no ser necesarios para la ejecución:

- `doc/`, `.git/`
- `.gitignore` , `Poles.zip`
- `ExampleAnalysis.py`, `ExampleSimulation.py`
- `ExampleAnalysis.m`, `ExampleSimulation.m`
- `model2018.m`, `run_model2018.py`
- `build.bat`, `license.txt`
## Atribución

Modelo original: **Verhulst et al. 2018**
> S. Verhulst, A. Altoè, V. Vasilkov — *Computational modeling of the human auditory periphery*, 2018.
> Repositorio: https://github.com/HearingTechnology/Verhulstetal2018Model