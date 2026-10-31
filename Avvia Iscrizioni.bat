@echo off
cd /d "%~dp0"
title Iscrizioni Pro Loco
echo Avvio del programma Iscrizioni Pro Loco...
python avvia.py
if errorlevel 1 pause
