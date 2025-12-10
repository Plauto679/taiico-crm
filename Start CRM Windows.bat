@echo off
cd /d "%~dp0"

echo Starting Taiico CRM...

:: Start Backend in new window
start "Taiico Backend" cmd /k "cd backend && python main.py"

:: Start Frontend in new window
start "Taiico Frontend" cmd /k "npm run dev"

echo Waiting for services to start...
timeout /t 5

:: Open Browser
start http://localhost:3000
