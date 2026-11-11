@echo off
chcp 65001 > nul
title Buscador de Vagas com IA - Iniciando...

echo ===================================================
echo     Iniciando seu Agente de Vagas Inteligente
echo ===================================================
echo.

cd /d "%~dp0"

if exist "venv\Scripts\python.exe" (
    echo Abrindo aplicacao...
    venv\Scripts\python.exe run.py
    goto end
)

echo Verificando ambiente Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao foi encontrado no seu computador!
    echo Por favor, instale o Python em https://www.python.org/downloads/
    echo Lembre-se de marcar a opcao "Add Python to PATH" durante a instalacao.
    pause
    exit /b 1
)

echo Configurando ambiente na primeira execucao (isso leva apenas 1 minuto)...
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt

echo.
echo Iniciando aplicacao...
venv\Scripts\python.exe run.py

:end
pause
