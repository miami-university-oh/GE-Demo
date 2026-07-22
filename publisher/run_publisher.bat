@echo off
rem CAM01 publisher launcher. First run creates the Python environment, then streams.
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    echo First run: creating Python environment...
    python -m venv .venv
    if errorlevel 1 goto :fail
    ".venv\Scripts\python.exe" -m pip install --quiet -r publisher\requirements.txt
    if errorlevel 1 goto :fail
)

".venv\Scripts\python.exe" publisher\cam01_publisher.py
exit /b

:fail
echo Setup failed. Ensure Python 3 is installed and on PATH.
exit /b 1
