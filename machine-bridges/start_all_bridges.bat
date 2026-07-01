@echo off
title IIoT Machine Bridges — Advanced Manufacturing Hub
color 0A

echo ============================================================
echo   IIoT Machine Bridges — Advanced Manufacturing Hub
echo   Haas TL-1 (ws://0.0.0.0:8765) + UR5e (ws://0.0.0.0:8766)
echo ============================================================
echo.

:: Check Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.9+ from https://python.org
    pause
    exit /b 1
)

:: Install dependencies if needed
echo [SETUP] Installing Python dependencies...
pip install websockets --quiet
echo [SETUP] Dependencies OK.
echo.

:: Launch Haas TL-1 bridge in a new window
echo [START] Launching Haas TL-1 bridge on port 8765...
start "Haas TL-1 Bridge" cmd /k "color 0B && title Haas TL-1 Bridge && python haas_bridge.py"

:: Small delay to avoid port conflicts
timeout /t 2 /nobreak >nul

:: Launch UR5e bridge in a new window
echo [START] Launching UR5e Cobot bridge on port 8766...
start "UR5e Cobot Bridge" cmd /k "color 0D && title UR5e Cobot Bridge && python ur5e_bridge.py"

echo.
echo [OK] Both bridges are running in separate windows.
echo      Haas TL-1  → ws://192.168.1.16:8765
echo      UR5e Cobot → ws://192.168.1.16:8766
echo.
echo      Open the IIoT Dashboard and navigate to the Makino Lab.
echo      Equipment panels will switch from simulation to LIVE data automatically.
echo.
echo [TIP] To stop all bridges, close the two bridge windows.
echo.
pause
