@echo off
title Price List Sync - Setup
cd /d "%~dp0"
echo.
echo  Price List Sync - one-time setup
echo  ================================
echo.
set PY=python
where py >nul 2>nul && set PY=py -3
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo  Python is not installed. Install it from https://www.python.org/downloads/
  echo  ^(tick "Add python.exe to PATH"^), then run setup again.
  pause
  exit /b 1
)
echo  [1/3] Installing what the tool needs...
%PY% -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo  Couldn't install. Check the internet connection and run setup again.
  pause
  exit /b 1
)
if not exist config.env copy /y config.env.example config.env >nul
echo  [2/3] Your settings: Notepad will open. Fill in the emails and Gmail details,
echo        then SAVE (Ctrl+S) and CLOSE Notepad.
:edit
start /wait notepad config.env
%PY% sync.py --check
if errorlevel 1 (
  echo  Notepad will open again so you can fix the items above.
  pause
  goto :edit
)
echo  [3/3] Turning on the weekly run...
%PY% sync.py --install-schedule
echo.
echo  All set. Double-click "send test email.bat" to see the report in your inbox.
pause
