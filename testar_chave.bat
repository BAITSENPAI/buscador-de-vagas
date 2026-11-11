@echo off
chcp 65001 > nul
title Diagnostico da Chave do Gemini

cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe testar_chave.py
) else (
    python testar_chave.py
)
