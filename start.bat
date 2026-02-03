@echo off
echo ================================
echo HR Assistant RAG Chat Interface
echo ================================
echo.
echo Choose what to start:
echo 1. Backend (FastAPI) only
echo 2. Frontend (React) only  
echo 3. Both (Backend + Frontend)
echo 4. Exit
echo.
set /p choice="Enter your choice (1-4): "

if "%choice%"=="1" (
    echo Starting FastAPI backend...
    .\.myenv\Scripts\python.exe main.py
) else if "%choice%"=="2" (
    echo Starting React frontend...
    cd frontend
    call npm start
) else if "%choice%"=="3" (
    echo Starting both services...
    echo.
    echo [1/2] Starting FastAPI backend in new window...
    start "HR Assistant Backend" .\.myenv\Scripts\python.exe main.py
    echo.
    echo [2/2] Starting React frontend...
    cd frontend
    call npm start
) else if "%choice%"=="4" (
    exit /b 0
) else (
    echo Invalid choice. Please try again.
    goto :eof
)
