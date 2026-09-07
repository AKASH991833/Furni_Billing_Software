@echo off
rem Build the Furniture Bill desktop app into dist/FurnitureBill/
cd /d "%~dp0"

pyinstaller --clean --noconfirm FurnitureBill.spec

if errorlevel 1 (
    echo BUILD FAILED
    exit /b 1
)

echo.
echo Build complete: dist\FurnitureBill\FurnitureBill.exe
echo Share the dist\FurnitureBill folder with your customer.
pause