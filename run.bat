@echo off
title Price List Sync
cd /d "%~dp0"
set PY=python
where py >nul 2>nul && set PY=py -3
%PY% sync.py
echo.
if exist reports start "" explorer reports
pause
