@echo off
chcp 65001 > nul
title Buscador de Normas (clara.nz)
echo ========================================================
echo   Iniciando o Buscador de Normas Tecnicas (clara.nz)
echo   Total de 27.988 normas catalogadas
echo ========================================================
echo.
echo Abrindo o navegador em http://localhost:8080 ...
echo (Para encerrar, basta fechar esta janela)
echo.
start http://localhost:8080
python app.py
pause
