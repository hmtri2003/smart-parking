@echo off
chcp 65001 >NUL
SET PYTHONUTF8=1
TITLE Quan Ly Bai Giu Xe Thong Minh (Portable Windows)

SET "SCRIPT_DIR=%~dp0"
CD /D "%SCRIPT_DIR%"

ECHO ============================================================
ECHO  KHOI DONG HE THONG QUAN LY BAI XE (PORTABLE WINDOWS)
ECHO  Thu muc chay: %SCRIPT_DIR%
ECHO ============================================================

SET "VENV_DIR=%SCRIPT_DIR%.venv"
SET "PYTHON_BIN=%VENV_DIR%\Scripts\python.exe"

:: 1. Kiem tra moi truong ao .venv
IF NOT EXIST "%PYTHON_BIN%" (
    ECHO [!] Dang khoi tao moi truong Python ao .venv tren Windows...
    python -m venv "%VENV_DIR%"
    IF ERRORLEVEL 1 (
        py -m venv "%VENV_DIR%"
    )
)

IF NOT EXIST "%PYTHON_BIN%" (
    SET "PYTHON_BIN=python"
)

:: 2. Kiem tra thu vien da cai dat day du chua
ECHO [+] Dang kiem tra thu vien...
"%PYTHON_BIN%" -c "import PyQt6, ultralytics, cv2" >NUL 2>&1
IF ERRORLEVEL 1 (
    ECHO [!] Dang tu dong cai dat thu vien tu requirements.txt...
    "%PYTHON_BIN%" -m pip install --upgrade pip
    "%PYTHON_BIN%" -m pip install -r "%SCRIPT_DIR%requirements.txt"
)

ECHO [+] Dang khoi chay ung dung...
"%PYTHON_BIN%" "%SCRIPT_DIR%main.py"

IF ERRORLEVEL 1 (
    ECHO.
    ECHO [!] Ung dung ket thuc voi ma loi %ERRORLEVEL%.
)

PAUSE