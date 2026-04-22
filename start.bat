@echo off
echo Запускаем бэкенд и LightRAG веб-интерфейс...

start "Backend API" cmd /k "cd /d %~dp0 && .venv\Scripts\python.exe -m app"
timeout /t 3 /nobreak >nul
start "LightRAG WebUI" cmd /k "cd /d %~dp0 && .venv\Scripts\python.exe webui_lightrag.py"

echo.
echo Бэкенд:           http://localhost:8000
echo LightRAG Web UI:  http://localhost:9621/webui
echo.
