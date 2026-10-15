@echo off
rem Command-line tile maker. Example: mixo photo.jpg --corners "510,564 2616,534 2514,2508 594,2478" --format 3mftex
set "PY="
for %%v in (3.13 3.12 3.11) do if not defined PY py -%%v --version >nul 2>nul && set "PY=py -%%v"
if not defined PY where py >nul 2>nul && set "PY=py -3"
if not defined PY set "PY=python"
%PY% "%~dp0scripts\mixo.py" %*
