@echo off
chcp 65001 > nul
title Servidor Web - PRO-ELÉTRICA CAD NBR 5410
cls
echo ====================================================================
echo   Iniciando Servidor Web Local - PRO-ELETTRICA CAD NBR 5410
echo ====================================================================
echo.

set "PY_EXE=C:\Users\agath\AppData\Local\Programs\PythonCodingPack\python.exe"

if exist "%PY_EXE%" (
    "%PY_EXE%" servidor_local.py
) else (
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        python servidor_local.py
    ) else (
        echo [ERRO] Python nao foi encontrado automaticamente.
        echo Por favor instale o Python ou execute atraves do PowerShell.
        pause
    )
)
pause
