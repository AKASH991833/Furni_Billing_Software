@echo off
rem Creates a Desktop Shortcut for Furniture Bill Software on any Windows PC
cd /d "%~dp0"

set "TARGET_EXE=%~dp0FurnitureBill.exe"
set "SHORTCUT_NAME=Furniture Bill Software.lnk"
set "ICON_FILE=%TARGET_EXE%"

echo Creating desktop shortcut with furniture icon...
powershell -NoProfile -Command "$dt = [Environment]::GetFolderPath('Desktop'); $ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut((Join-Path $dt '%SHORTCUT_NAME%')); $s.TargetPath = '%TARGET_EXE%'; $s.WorkingDirectory = '%~dp0'; $s.IconLocation = '%ICON_FILE%,0'; $s.Description = 'Furniture Billing & Quotation Software'; $s.Save(); Write-Output ('Shortcut saved to: ' + (Join-Path $dt '%SHORTCUT_NAME%'))"

echo.
echo [SUCCESS] Desktop shortcut created successfully with luxury furniture icon!
pause

