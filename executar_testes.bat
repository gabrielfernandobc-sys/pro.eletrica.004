@echo off
chcp 65001 > nul
title Suíte de Testes Automatizados - PRO-ELÉTRICA CAD NBR 5410
echo ==============================================================================
echo    INICIANDO SUÍTE OFICIAL DE TESTES - PRO-ELÉTRICA CAD NBR 5410
echo ==============================================================================
echo.
python suite_testes_pro_eletrica.py
echo.
echo ==============================================================================
echo    Execução finalizada. Pressione qualquer tecla para sair.
echo ==============================================================================
pause > nul
