#!/bin/bash
# Avvio del programma Iscrizioni su Linux.
# Usa l'ambiente Python della cartella .venv se c'e', altrimenti python3.
cd "$(dirname "$0")"
if [ -x ".venv/bin/python" ]; then
    exec ".venv/bin/python" avvia.py
else
    exec python3 avvia.py
fi
