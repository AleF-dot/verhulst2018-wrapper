FROM python:3.11-slim

# Dependencias del sistema y herramientas de compilación para el modelo
RUN apt-get update  && DEBIAN_FRONTEND=noninteractive && apt-get install -y \
    build-essential \
    gcc \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    unzip \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo
WORKDIR /app

# Copiar el modelo y la API dentro del contenedor
COPY Verhulstetal2018Model/ Verhulstetal2018Model/
COPY SimulationAPI.py SimulationAPI.py

# Dependencias de Python (modelo + API web)
RUN pip install --upgrade pip && \
    pip install numpy scipy matplotlib fastapi uvicorn[standard]

# Intentar descomprimir Poles (no falla si ya está descomprimido)
RUN cd Verhulstetal2018Model && unzip -q Poles.zip || true

# Normalizar build.sh y compilar librería nativa (tridiag.so)
RUN cd Verhulstetal2018Model && sed -i 's/\r$//' build.sh && bash build.sh

# Los módulos del repo son importables desde SimulationAPI.py
ENV PYTHONPATH="/app/Verhulstetal2018Model"

# Exponer puerto 8000
EXPOSE 8000

# Levantar servidor Uvicorn/FastAPI
CMD ["uvicorn", "SimulationAPI:app", "--host", "0.0.0.0", "--port", "8000"]