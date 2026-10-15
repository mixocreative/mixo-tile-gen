@echo off
rem Double-click to run mixo-tile-gen on this PC. Add "phone" (or use start-windows-phone.bat) for a phone link.
title mixo-tile-gen
cd /d "%~dp0"
set "PY="
for %%v in (3.13 3.12 3.11) do if not defined PY py -%%v --version >nul 2>nul && set "PY=py -%%v"
if not defined PY where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo Python is not installed. Get it from https://www.python.org/downloads/
  echo During setup tick "Add python.exe to PATH", then double-click this file again.
  start "" https://www.python.org/downloads/
  pause
  exit /b 1
)
if /i "%~1"=="phone" (%PY% scripts\run_local.py --phone) else (%PY% scripts\run_local.py)
pause
