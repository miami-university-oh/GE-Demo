@echo off
title RealSense L515 RGB Stream — CAM-01
color 0A

echo ============================================
echo   RealSense L515 RGB Stream — CAM-01
echo   Stream URL: http://192.168.1.16:5001/video_feed
echo ============================================
echo.

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.8+
    pause
    exit /b 1
)

:: Install dependencies if needed
echo Checking dependencies...
pip install flask pyrealsense2 opencv-python numpy --quiet

echo.
echo Starting RealSense stream server...
echo Press Ctrl+C to stop.
echo.

python "%~dp0realsense_stream.py"

pause
