# ======================================================
# Stage 1: build — compilación y dependencias
# ======================================================
FROM python:3.11-slim AS builder

# Toolchain de compilación — solo necesario para construir tridiag.so
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    build-essential \
    gcc \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo
WORKDIR /app

# Copiar el modelo dentro del contenedor
COPY Verhulstetal2018Model/ Verhulstetal2018Model/

# Dependencias de Python (modelo + API web)
RUN pip install --upgrade pip && \
    pip install numpy scipy matplotlib fastapi uvicorn[standard]

# Intentar descomprimir Poles (no falla si ya está descomprimido)
RUN cd Verhulstetal2018Model && unzip -q Poles.zip || true

# Normalizar build.sh y compilar librería nativa (tridiag.so)
RUN cd Verhulstetal2018Model && sed -i 's/\r$//' build.sh && bash build.sh


# ======================================================
# Stage 2: runtime — imagen final sin toolchain
# ======================================================
FROM python:3.11-slim

# Solo dependencias runtime de tridiag.so — sin gcc, gfortran, headers
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    libopenblas0 \
    libgfortran5 \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo
WORKDIR /app

# Copiar solo lo necesario desde el stage builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY --from=builder /app/Verhulstetal2018Model /app/Verhulstetal2018Model

# Copiar la API
COPY SimulationAPI.py SimulationAPI.py

# Los módulos del modelo son importables desde SimulationAPI.py
ENV PYTHONPATH="/app/Verhulstetal2018Model"

# Exponer puerto 8000
EXPOSE 8000

# Levantar servidor Uvicorn/FastAPI
CMD ["uvicorn", "SimulationAPI:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]