@echo off
rem Fandom Exporter: double-click to run. Extra arguments are passed to the program (e.g. --redownload).
cd /d "%~dp0"

rem "python" may be the Microsoft Store stub that is there even without Python, so check that it really runs.
set "PY="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if not defined PY (
    python --version >nul 2>&1
    if not errorlevel 1 set "PY=python"
)
if not defined PY (
    echo Python not found. Install Python 3.10+ from python.org and enable "Add python.exe to PATH".
    pause
    exit /b 1
)

%PY% -c "import requests, bs4, markdownify" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies from requirements.txt...
    %PY% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Could not install dependencies. Run: pip install -r requirements.txt
        pause
        exit /b 1
    )
)

rem The program itself waits for Enter at the end when it asked for the wiki address.
%PY% fandom_exporter.py %*
