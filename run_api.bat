@echo off
REM Activate venv and run the API with uvicorn
call .\.venv\Scripts\activate.bat
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
pause
