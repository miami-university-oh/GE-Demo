@echo off
title IIoT Dashboard — Python Dependency Installer
color 0A

echo ============================================================
echo   IIoT Dashboard — Python Dependency Installer
echo ============================================================
echo.

:: Check Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo         Please install Python 3.9+ from https://python.org
    echo         Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo [OK] Python found:
python --version
echo.

:: Check pip is available
pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip not found. Try running: python -m ensurepip
    pause
    exit /b 1
)

echo [INSTALLING] Installing all Python dependencies...
echo             This may take a few minutes on first run.
echo.

pip install -r "%~dp0requirements.txt"

if errorlevel 1 (
    echo.
    echo [WARNING] One or more packages failed to install.
    echo           pyrealsense2 and ur-rtde require specific hardware drivers.
    echo           If you don't have a RealSense camera or UR5e robot, those
    echo           errors are safe to ignore.
    echo.
) else (
    echo.
    echo [OK] All dependencies installed successfully.
    echo.
)

echo ============================================================
echo   Next Steps:
echo     1. Install Node.js from https://nodejs.org (LTS version)
echo     2. Install pnpm: npm install -g pnpm
echo     3. Install JS dependencies: pnpm install (in project folder)
echo     4. Start the dashboard: pnpm dev
echo ============================================================
echo.
pause
