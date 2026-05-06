#!/bin/bash

set -e

echo "Verificando entorno..."

# Verificar git
if ! command -v git &> /dev/null; then
    echo ""
    echo "git no esta instalado."
    echo "Instala con: sudo apt install git  (Debian/Ubuntu)"
    echo "             sudo dnf install git  (Fedora)"
    echo "             sudo pacman -S git    (Arch)"
    echo ""
    exit 1
fi

# Verificar unzip
if ! command -v unzip &> /dev/null; then
    echo ""
    echo "unzip no esta instalado."
    echo "Instala con: sudo apt install unzip            (Debian/Ubuntu)"
    echo "             sudo dnf install unzip            (Fedora)"
    echo "             sudo pacman -S unzip              (Arch)"
    echo ""
    exit 1
fi

# Verificar gcc
if ! command -v gcc &> /dev/null; then
    echo ""
    echo "gcc no esta instalado."
    echo "Instala con: sudo apt install build-essential  (Debian/Ubuntu)"
    echo "             sudo dnf install gcc              (Fedora)"
    echo "             sudo pacman -S base-devel         (Arch)"
    echo ""
    exit 1
fi

# Verificar gfortran
if ! command -v gfortran &> /dev/null; then
    echo ""
    echo "gfortran no esta instalado."
    echo "Instala con: sudo apt install gfortran          (Debian/Ubuntu)"
    echo "             sudo dnf install gcc-gfortran      (Fedora)"
    echo "             sudo pacman -S gcc-fortran         (Arch)"
    echo ""
    exit 1
fi

# Clonar repo si no existe
if [ ! -d "Verhulstetal2018Model" ]; then
    echo ""
    echo "Clonando repositorio..."
    git clone https://github.com/HearingTechnology/Verhulstetal2018Model
fi

# Limpiar directorio del modelo
echo ""
echo "Limpiando directorio del modelo..."
MODEL=Verhulstetal2018Model

for target in \
    "$MODEL/doc" \
    "$MODEL/.git" \
    "$MODEL/.gitignore" \
    "$MODEL/ExampleAnalysis.py" \
    "$MODEL/ExampleSimulation.py" \
    "$MODEL/ExampleAnalysis.m" \
    "$MODEL/ExampleSimulation.m" \
    "$MODEL/model2018.m" \
    "$MODEL/run_model2018.py" \
    "$MODEL/build.bat" \
    "$MODEL/license.txt"
do
    if [ -e "$target" ]; then
        rm -rf "$target"
        echo "[+] Borrado: $target"
    fi
done

# Descomprimir Poles y borrar el zip
if [ -f "$MODEL/Poles.zip" ]; then
    echo ""
    echo "Descomprimiendo Poles.zip..."
    unzip -q "$MODEL/Poles.zip" -d "$MODEL"
    rm "$MODEL/Poles.zip"
    echo "[+] Poles descomprimido y zip eliminado"
fi

# Verificar Docker
if ! docker info &> /dev/null; then
    echo ""
    echo "Docker no esta corriendo o no esta instalado."
    echo "Instala desde: https://docs.docker.com/engine/install/"
    echo ""
    exit 1
fi

# Ejecucion
echo "Levantando contenedor... (Ctrl+C para detener)"
docker compose up --build