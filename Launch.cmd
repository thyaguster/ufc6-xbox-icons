@echo off
setlocal
cd /d "%~dp0"
if exist "UFC6-Xbox-Icons.exe" (
    start "" "%~dp0UFC6-Xbox-Icons.exe"
    exit /b 0
)
where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%~dp0xbox_icons.py"
    if not errorlevel 1 exit /b 0
    echo The patcher could not start. Python 3.10+ with Tkinter is required.
    pause
    exit /b 1
)
where python >nul 2>nul
if not errorlevel 1 (
    python "%~dp0xbox_icons.py"
    if not errorlevel 1 exit /b 0
)
echo Install Python 3.10+ with Tkinter, or download the Windows executable release.
pause
exit /b 1
