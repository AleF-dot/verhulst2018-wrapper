@echo off

REM Corre la API localmente sin Docker.
REM Requiere gcc en el PATH para compilar tridiag.so.
REM El uso de --reload esta atado unicamente a contexto de desarrollo.

:: Verificar gcc
gcc --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo gcc no encontrado en el PATH.
    echo Para compilar tridiag.so localmente necesitas MinGW-w64.
    echo Descargalo desde: https://www.mingw-w64.org/downloads/
    echo O usa setup.bat para correr el modelo via Docker.
    echo.
    pause
    exit /b
)

:: Compilar tridiag.dll si no existe
IF NOT EXIST Verhulstetal2018Model\tridiag.dll (
    echo.
    echo Compilando tridiag.dll...
    cd Verhulstetal2018Model
    gcc -shared -fpic -O3 -ffast-math -o tridiag.dll cochlea_utils.c
    cd ..
    IF NOT EXIST Verhulstetal2018Model\tridiag.dll (
        echo [!] Error al compilar tridiag.dll
        pause
        exit /b
    )
    echo [+] tridiag.dll compilado
)

:: Crear venv si no existe
IF NOT EXIST .venv (
    echo.
    echo Creando entorno virtual...
    python -m venv .venv
    IF %ERRORLEVEL% NEQ 0 (
        echo [!] Error al crear el entorno virtual. Verificá que Python esta instalado.
        pause
        exit /b
    )
)

:: Activar venv e instalar dependencias
call .\.venv\Scripts\activate.bat

echo.
echo Instalando dependencias...
pip install -r requirements.txt --quiet
IF %ERRORLEVEL% NEQ 0 (
    echo [!] Error al instalar dependencias.
    pause
    exit /b
)

:: Levantar API
echo.
echo Levantando API... (Ctrl+C para detener)
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

pause