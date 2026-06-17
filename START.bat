@echo off
echo Iniciando backend de Trading App...
cd /d "%~dp0"
call venv\Scripts\activate 2>nul || echo Sin venv, usando Python global
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
