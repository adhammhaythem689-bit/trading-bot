@echo off
rem Double-click this file to open the trading bot dashboard.
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo First run: setting up, this takes a minute...
    python -m venv venv || goto :error
    "venv\Scripts\python.exe" -m pip install -q -r requirements.txt || goto :error
)

echo Opening the dashboard in your browser. Keep this window open while you use it.
"venv\Scripts\python.exe" dashboard.py --open
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo Something went wrong starting the dashboard. The message above says what.
pause
exit /b 1
