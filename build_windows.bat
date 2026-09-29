@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows.ps1"
if errorlevel 1 (
  echo.
  echo Build fehlgeschlagen.
  pause
  exit /b 1
)
echo.
echo Build erfolgreich. Siehe Ordner "release".
pause
endlocal
