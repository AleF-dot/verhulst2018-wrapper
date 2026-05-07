# 03/05/2026
[x] Atomizar las simulaciones y organizarlas por carpeta en el volumen compartido
[x] Verificar las salidas del modelo, cambiar su comportamiento para que apunten al volumen compartido
[x] Analizar dependencias de StartingPoles.dat
[x] Analizar dependencia de OHC_ind.py sobre el directorio "mat files" (diferido — no integrado aún)
[x] IMPORTANTE documentar en README.md los archivos borrados + atribución a Verhulst et al. 2018

# 04/05/2026
[x] Verificar si /simulate/batch necesita ParallelRAMSimulationsEFR (no — son casos de uso distintos)
[x] Resolver bug de anfH con storeflag='w' (workaround: forzar 'b')
[x] Multi-stage build en Dockerfile
[x] Límites de recursos en docker-compose.yaml
[x] PYTHONUNBUFFERED=1 en docker-compose.yaml (prints bloqueantes durante simulación)
[x] Pendiente setear PYTHONUNBUFFERED=1 en Dockerfile
[x] Exponer w1, w3, w5 como respuesta de la API
[x] EFR_combined.flatten() se llama de nuevo en el gráfico (t_efr y axes[0,1]) siendo que ya viene 1D de _calculate_efr. No rompe nada, pero es redundante.
[x] Carpeta huérfana cuando un worker muere durante la simulación (rmtree no corre si el proceso es killeado)
[ ] Verificar si el worker siempre muere en la primera simulación o fue puntual
[ ] Contemplar posibilidad de patch local a model2018.py línea 251 (workaround actual: forzar 'b' en storeflag)
[ ] OHC_ind.py + mat files/ en el contenedor (habilita perfiles auditivos desde audiogramas clínicos reales)
[ ] Decidir objetivo científico — necesario para actualizar dashboard y esquema de base de datos

# 06/05/2026
[x] logging estructurado — migración de print() a logger.info/error con basicConfig en main.py
[x] Instrumentación de model2018(): tiempo (perf_counter), CPU (psutil) y RAM pico (thread 100ms)
[x] try/finally alrededor de model2018() — thread de muestreo se detiene ante excepciones
[x] logger.exception en except — loguea traceback completo
[x] MAX_WORKERS configurable via variable de entorno (docker-compose.yaml)
[x] @app.on_event('startup') reemplazado por lifespan (asynccontextmanager)
[x] psutil agregado a requirements.txt
[x] Logger de batch en routes.py — tiempo total y cantidad de simulaciones (descartar al implementar colas)
[ ] Celery + Redis — cola de trabajo para manejar concurrencia real (objetivo 100+ requests)
[ ] async task pattern — POST /simulate devuelve task_id, GET /task/{task_id} para polling