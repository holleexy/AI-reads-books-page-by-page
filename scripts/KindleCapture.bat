@echo off
setlocal
cd /d "%~dp0"
title Kindle capture
echo Open the Kindle book, then choose direction.
echo R = Right page-turn
echo L = Left page-turn
choice /c RL /n /m "Press R or L: "
if errorlevel 255 goto :eof
if errorlevel 2 goto LEFT
if errorlevel 1 goto RIGHT
goto :eof

:RIGHT
set DIR=Right
goto RUN

:LEFT
set DIR=Left
goto RUN

:RUN
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0kindle_capture.ps1" -Direction %DIR%
echo.
pause
