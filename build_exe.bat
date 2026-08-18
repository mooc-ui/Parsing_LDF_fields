@echo off
setlocal
title LIN Signal Mapping Generator - Build EXE

cd /d "%~dp0"

echo ============================================
echo   LIN Signal Mapping Generator - One-click Build
echo ============================================
echo.

REM ---- 1. locate Python ----
set "PY="
where python >nul 2>nul
if %errorlevel%==0 (
    set "PY=python"
) else (
    where py >nul 2>nul
    if %errorlevel%==0 (
        set "PY=py"
    )
)
if "%PY%"=="" (
    echo [ERROR] Python not found. Please install Python 3.9+ and check "Add to PATH".
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/2] Checking PyInstaller ...
%PY% -c "import PyInstaller" >nul 2>nul
if %errorlevel% neq 0 (
    echo        Not installed. Installing PyInstaller ...
    %PY% -m pip install pyinstaller
    if %errorlevel% neq 0 (
        echo [ERROR] PyInstaller install failed. Check your network and retry.
        pause
        exit /b 1
    )
)
echo        PyInstaller ready.

echo [2/2] Building (1-3 min, please do not close) ...
echo.
%PY% build_exe.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed. See logs above.
    pause
    exit /b 1
)

echo.
echo Build finished!
echo EXE: %~dp0dist\LIN_Signal_Mapping_Generator.exe
echo.
pause