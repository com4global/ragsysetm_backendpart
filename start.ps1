# HR Assistant RAG Chat Interface Startup Script

Write-Host "================================" -ForegroundColor Cyan
Write-Host "HR Assistant RAG Chat Interface" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Choose what to start:" -ForegroundColor Green
Write-Host "1. Backend (FastAPI) only"
Write-Host "2. Frontend (React) only"
Write-Host "3. Both (Backend + Frontend)"
Write-Host "4. Exit"
Write-Host ""

$choice = Read-Host "Enter your choice (1-4)"

switch($choice) {
    "1" {
        Write-Host "Starting FastAPI backend..." -ForegroundColor Yellow
        Write-Host "API will be available at http://localhost:8000" -ForegroundColor Cyan
        & .\.myenv\Scripts\python.exe main.py
    }
    "2" {
        Write-Host "Starting React frontend..." -ForegroundColor Yellow
        Push-Location frontend
        & npm start
        Pop-Location
    }
    "3" {
        Write-Host "Starting both services..." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "[1/2] Starting FastAPI backend in new window..." -ForegroundColor Green
        Write-Host "API will be available at http://localhost:8000" -ForegroundColor Cyan
        
        # Start backend in a new PowerShell window
        Start-Process powershell -ArgumentList {
            Push-Location $PSScriptRoot
            .\.myenv\Scripts\python.exe main.py
        }
        
        Write-Host "[2/2] Waiting a moment for backend to start..." -ForegroundColor Green
        Start-Sleep -Seconds 2
        
        Write-Host "Starting React frontend..." -ForegroundColor Yellow
        Write-Host "Frontend will be available at http://localhost:3000" -ForegroundColor Cyan
        Push-Location frontend
        & npm start
        Pop-Location
    }
    "4" {
        Write-Host "Goodbye!" -ForegroundColor Green
        exit
    }
    default {
        Write-Host "Invalid choice. Please run the script again." -ForegroundColor Red
    }
}
