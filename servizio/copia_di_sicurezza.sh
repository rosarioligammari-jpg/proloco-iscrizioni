#!/bin/bash
# Copia di sicurezza dell'archivio delle iscrizioni.
#
# PRIMA DI USARLO: controlla se le copie di /srv/app-dati sono gia' fatte
# da qualcos'altro su questo server. Se lo sono, questo script non serve.
#
# Uso:    ./copia_di_sicurezza.sh [cartella-dati] [cartella-copie]
# Senza argomenti lavora sulla cartella del programma (uso locale).
# Sul server:
#     /srv/app/iscrizioni/prod/servizio/copia_di_sicurezza.sh \
#         /srv/app-dati/iscrizioni/prod /srv/archivio/iscrizioni
#
# Tiene le ultime 30 copie e butta le piu' vecchie.

set -u
DATI="${1:-$(cd "$(dirname "$0")/.." && pwd)/dati}"
COPIE="${2:-$DATI/copie}"
QUANDO="$(date +%Y-%m-%d_%H%M)"

if [ ! -f "$DATI/iscrizioni.sqlite" ]; then
    echo "ERRORE: non trovo $DATI/iscrizioni.sqlite"; exit 1
fi
mkdir -p "$COPIE" || exit 1

# .backup di sqlite3 copia il file in modo sicuro anche a programma acceso.
if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$DATI/iscrizioni.sqlite" ".backup '$COPIE/iscrizioni_$QUANDO.sqlite'" || exit 1
else
    cp "$DATI/iscrizioni.sqlite" "$COPIE/iscrizioni_$QUANDO.sqlite" || exit 1
fi
echo "copia fatta: $COPIE/iscrizioni_$QUANDO.sqlite"

ls -1t "$COPIE"/iscrizioni_*.sqlite 2>/dev/null | tail -n +31 | while read -r vecchia; do
    rm -f "$vecchia"
done
