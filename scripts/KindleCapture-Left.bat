@echo off
setlocal
cd /d "%~dp0"
title Kindle capture Left
echo Open the Kindle book, then wait. Left-turn capture starts in 5 seconds.
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0kindle_capture.ps1" -Direction Left
echo.
pause
