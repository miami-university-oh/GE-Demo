@echo off
:: ============================================================
:: start_camera_proxy.bat
:: IIoT Dashboard - Camera Streaming Proxy
:: ============================================================

title IIoT Camera Proxy - mediamtx

echo.
echo  ================================================
echo   IIoT Building Dashboard - Camera Proxy
echo   Server: 192.168.1.16
echo   HLS Output: http://192.168.1.16:18888
echo  ================================================
echo.
echo  Streams available after startup:
echo    CAM-02 Amcrest:   http://192.168.1.16:18888/cam02/index.m3u8
echo    CAM-01 RealSense: http://192.168.1.16:18888/cam01/index.m3u8
echo    API status:       http://192.168.1.16:9997/v3/paths/list
echo.
echo  Press Ctrl+C to stop the proxy.
echo.

:: Check if mediamtx.exe exists in the same folder
if not exist "%~dp0mediamtx.exe" (
    echo  ERROR: mediamtx.exe not found in this folder.
    echo.
    echo  Please download mediamtx for Windows from:
    echo  https://github.com/bluenviron/mediamtx/releases/latest
    echo  Look for: mediamtx_vX.X.X_windows_amd64.zip
    echo  Extract mediamtx.exe into this folder, then run this script again.
    echo.
    pause
    exit /b 1
)

:: Launch mediamtx with our config
"%~dp0mediamtx.exe" "%~dp0mediamtx.yml"

echo.
echo  Proxy stopped.
pause
