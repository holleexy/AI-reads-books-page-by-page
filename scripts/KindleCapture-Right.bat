@echo off
setlocal
cd /d "%~dp0"
title Kindle capture Right
echo Open the Kindle book, then wait. Right-turn capture starts in 5 seconds.
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0kindle_capture.ps1" -Direction Right
echo.
pause
