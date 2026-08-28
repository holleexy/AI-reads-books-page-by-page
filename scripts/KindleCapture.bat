@echo off
setlocal
cd /d "%~dp0"
title Kindle capture
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0kindle_capture_gui.ps1"
echo.
pause
