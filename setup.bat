@echo off

echo Verificando entorno...

:: Verificar git
git --version >nul 2>&1

IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo Git no esta instalado.
    echo Descargalo desde:
    echo https://git-scm.com/download/win
    echo.
    pause
    exit /b
)

:: Clonar repo si no existe
IF NOT EXIST Verhulstetal2018Model (
    echo.
    echo Clonando repositorio...
    git clone https://github.com/HearingTechnology/Verhulstetal2018Model
)

:: Limpiar directorio del modelo
echo.
echo Limpiando directorio del modelo...
set MODEL=Verhulstetal2018Model
if exist %MODEL%\doc rmdir /s /q %MODEL%\doc
if exist %MODEL%\.git rmdir /s /q %MODEL%\.git
if exist %MODEL%\.gitignore del /q %MODEL%\.gitignore
if exist %MODEL%\ExampleAnalysis.py del /q %MODEL%\ExampleAnalysis.py
if exist %MODEL%\ExampleSimulation.py del /q %MODEL%\ExampleSimulation.py
if exist %MODEL%\ExampleAnalysis.m del /q %MODEL%\ExampleAnalysis.m
if exist %MODEL%\ExampleSimulation.m del /q %MODEL%\ExampleSimulation.m
if exist %MODEL%\model2018.m del /q %MODEL%\model2018.m
if exist %MODEL%\run_model2018.py del /q %MODEL%\run_model2018.py
if exist %MODEL%\build.bat del /q %MODEL%\build.bat
if exist %MODEL%\license.txt del /q %MODEL%\license.txt

:: Verificar Docker
docker info >nul 2>&1

IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo Docker no esta corriendo o no esta instalado.
    echo Si no esta instalado, descargalo desde:
    echo https://docs.docker.com/desktop/setup/install/windows-install
    pause
    exit /b
)

:: Ejecución
echo Ejecutando Contenedor...
docker compose up --build

IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Hubo un error al levantar el contenedor (es posible que ya exista un contenedor).
    echo.
) ELSE (
    echo.
    echo [+] Contenedor levantado exitosamente.
)

pause