@echo off
echo Installing backend dependencies...
echo.
cd /d "%~dp0"

REM Use the venv Python directly to ensure we install into .myenv
".\.myenv\Scripts\python.exe" -m pip install --upgrade pip
".\.myenv\Scripts\python.exe" -m pip install openai pinecone python-dotenv pypdf fastapi uvicorn openpyxl python-docx pandas

echo.
echo Verifying openai...
".\.myenv\Scripts\python.exe" -c "import openai; print('openai OK')"
echo.
echo Verifying pinecone...
".\.myenv\Scripts\python.exe" -c "import pinecone; print('pinecone OK')"
echo.
echo Done. Restart the backend with: python -m uvicorn main:app --reload --port 8000
pause
