@echo off
cd /d "%~dp0.."
echo ==================================================
echo Starting Local AI RAG Studio
echo ==================================================

echo [1/3] Starting Firecrawl Docker containers (Web Scraper)...
docker compose -f infra\firecrawl-docker-compose.yaml up -d

echo [2/3] Starting Python Backend API and React Frontend in Windows Terminal...
wt new-tab --title "Backend API" -d . cmd /k "venv\Scripts\activate && python -m uvicorn backend.app.api:app --reload" ; new-tab --title "React Frontend" -d .\frontend cmd /k "npm run dev"

echo.
echo All services are starting! 
echo The frontend will be available at http://localhost:5173
echo.
pause
