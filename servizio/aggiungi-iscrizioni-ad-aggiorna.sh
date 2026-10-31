#!/bin/bash
# Insegna il programma «iscrizioni» al comando /usr/local/bin/aggiorna.
#
# Quel file serve a TUTTI i programmi dello studio: qui si tocca con i
# guanti. Copia di sicurezza prima, controllo della sintassi dopo, e se
# qualcosa non torna si rimette la copia e ci si ferma.
set -u

COMANDO=/usr/local/bin/aggiorna
COPIA=/usr/local/bin/aggiorna.prima-di-iscrizioni

if [ "$(id -u)" != "0" ]; then echo "Va lanciato con sudo."; exit 1; fi

if [ ! -f "$COMANDO" ]; then
  echo "ERRORE: non trovo $COMANDO. Non faccio niente."; exit 1
fi

if grep -q "iscrizioni/prod)" "$COMANDO"; then
  echo "Le iscrizioni ci sono gia' in $COMANDO. Non tocco niente."; exit 0
fi

if [ -e "$COPIA" ]; then
  echo "ERRORE: $COPIA esiste gia'. Non la sovrascrivo."; exit 1
fi

cp -p "$COMANDO" "$COPIA" || { echo "ERRORE: copia non riuscita. Fermo tutto."; exit 1; }
echo "-- copia di sicurezza fatta: $COPIA"

python3 - "$COMANDO" <<'PY'
import sys
percorso = sys.argv[1]
righe = open(percorso).read().splitlines(True)
nuove = [
    "  iscrizioni/prod) CLONE=/srv/app/iscrizioni/prod; COMPOSE=deploy/prod.yml; CONT=iscrizioni-reale; PORTA=8113; SALUTE=/salute ;;\n",
    "  iscrizioni/test) CLONE=/srv/app/iscrizioni/test; COMPOSE=deploy/test.yml; CONT=iscrizioni-prova; PORTA=8213; SALUTE=/salute ;;\n",
]
uscita, fatto = [], False
for r in righe:
    # La riga finale del blocco «case»: quella che dice «Non conosco...».
    if not fatto and r.lstrip().startswith("*)") and "Non conosco" in r:
        uscita.extend(nuove)
        fatto = True
    uscita.append(r)
if not fatto:
    sys.exit("ERRORE: non trovo la riga finale del blocco case (quella con 'Non conosco')")
open(percorso, "w").writelines(uscita)
print("-- due righe inserite prima della riga finale del blocco case")
PY

if [ $? -ne 0 ]; then
  echo "ERRORE nell inserimento. Rimetto la copia."; cp -p "$COPIA" "$COMANDO"; exit 1
fi

echo "-- controllo che il comando sia ancora scritto bene"
if ! bash -n "$COMANDO"; then
  echo "ERRORE: il comando non e' piu' valido. Rimetto la copia e mi fermo."
  cp -p "$COPIA" "$COMANDO"; exit 1
fi

echo "-- controllo che gli altri programmi siano ancora riconosciuti"
MANCANTI=0
for G in elmo/prod patenti/prod sossanita/prod proloco/prod mezzi/prod; do
  grep -q "$G)" "$COMANDO" || MANCANTI=$((MANCANTI+1))
done
if [ "$MANCANTI" -gt 0 ]; then
  echo "ERRORE: $MANCANTI programmi sono spariti dall'elenco. Rimetto la copia."
  cp -p "$COPIA" "$COMANDO"; exit 1
fi

echo
echo "FATTO. Da adesso funzionano:"
echo "   sudo aggiorna iscrizioni prod"
echo "   sudo aggiorna iscrizioni test"
echo
echo "Per tornare indietro:"
echo "   sudo cp -p $COPIA $COMANDO"
