@echo off
rem Master Production Build & Installer Script for Furniture Bill
cd /d "%~dp0"
python build_release.py
if errorlevel 1 (
    echo.
    echo =======================================================
    echo BUILD FAILED! Check error messages above.
    echo =======================================================
    pause
    exit /b 1
)
pause