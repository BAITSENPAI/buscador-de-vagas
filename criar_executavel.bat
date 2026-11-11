@echo off
chcp 65001 > nul
title Gerando Executavel (.exe) do Buscador de Vagas

echo ===================================================
echo     Gerando Executável Autônomo para Windows
echo ===================================================
echo.

cd /d "%~dp0"

echo Compilando com PyInstaller...
venv\Scripts\pyinstaller.exe --noconfirm --onedir --windowed --name "BuscadorDeVagas" --add-data "frontend;frontend" run.py

echo.
if exist "dist\BuscadorDeVagas\BuscadorDeVagas.exe" (
    echo ===================================================
    echo  SUCESSO! O executavel foi gerado em:
    echo  dist\BuscadorDeVagas\
    echo.
    echo  Voce pode compactar a pasta 'BuscadorDeVagas' em .zip
    echo  e compartilhar com qualquer pessoa!
    echo ===================================================
) else (
    echo [ERRO] Ocorreu uma falha ao gerar o executavel.
)

pause
