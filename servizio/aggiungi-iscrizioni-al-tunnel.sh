#!/bin/bash
# Aggiunge iscrizioni.clerm.it all'ingress di cloudflared.
#
# Scritto sulla stessa forma di ~/aggiungi-sossanita-al-tunnel.sh, che e'
# gia' in uso su questo server: copia di sicurezza prima di toccare,
# controllo della configurazione dopo, e a ogni verifica che non torna
# rimette la configurazione di prima e si ferma.
set -u

CFG=/etc/cloudflared/config.yml
COPIA=/etc/cloudflared/config.yml.prima-di-iscrizioni
PORTA=8113
NOME=iscrizioni.clerm.it

if [ "$(id -u)" != "0" ]; then echo "Va lanciato con sudo."; exit 1; fi

if grep -q "$NOME" "$CFG"; then
  echo "ERRORE: $NOME c'e' gia' in $CFG. Non tocco niente."; exit 1
fi
if [ -e "$COPIA" ]; then
  echo "ERRORE: $COPIA esiste gia'. Non la sovrascrivo."; exit 1
fi

echo "-- controllo che il programma risponda sulla porta $PORTA"
if ! curl -fs -o /dev/null "http://127.0.0.1:$PORTA/salute"; then
  echo "ERRORE: sulla porta $PORTA non risponde niente."
  echo "Prima si avvia il contenitore, poi si aggiunge al tunnel."
  exit 1
fi

cp -p "$CFG" "$COPIA" || { echo "ERRORE: copia non riuscita. Fermo tutto."; exit 1; }
echo "-- copia di sicurezza fatta: $COPIA"

python3 - "$CFG" "$NOME" "$PORTA" <<'PY'
import sys
percorso, nome, porta = sys.argv[1], sys.argv[2], sys.argv[3]
righe = open(percorso).read().splitlines(True)
uscita, fatto = [], False
for r in righe:
    if not fatto and r.strip() == "- service: http_status:404":
        uscita.append("  - hostname: %s\n" % nome)
        uscita.append("    service: http://127.0.0.1:%s\n" % porta)
        fatto = True
    uscita.append(r)
if not fatto:
    sys.exit("ERRORE: non trovo la regola finale '- service: http_status:404'")
open(percorso, "w").writelines(uscita)
print("-- voce inserita prima della regola finale")
PY

if [ $? -ne 0 ]; then
  echo "ERRORE nell inserimento. Rimetto la copia."; cp -p "$COPIA" "$CFG"; exit 1
fi

echo "-- controllo che lo YAML sia valido"
if ! python3 -c "import yaml; yaml.safe_load(open('$CFG'))"; then
  echo "ERRORE: YAML non valido. Rimetto la copia e mi fermo."; cp -p "$COPIA" "$CFG"; exit 1
fi

echo "-- controllo ingress di cloudflared"
if ! cloudflared --config "$CFG" tunnel ingress validate; then
  echo "ERRORE: ingress non valido. Rimetto la copia e mi fermo."; cp -p "$COPIA" "$CFG"; exit 1
fi

echo "-- riavvio cloudflared"
systemctl restart cloudflared
sleep 4
if ! systemctl is-active --quiet cloudflared; then
  echo "ERRORE: cloudflared non e attivo. Rimetto la copia e riavvio."
  cp -p "$COPIA" "$CFG"; systemctl restart cloudflared
  echo "Tornato indietro. Per capire:  journalctl -u cloudflared -n 40"; exit 1
fi

echo "-- controllo che gli altri indirizzi rispondano ancora"
GUASTI=0
for P in 8100 8105 8107 8109; do
  curl -fs -o /dev/null --max-time 5 "http://127.0.0.1:$P/" || GUASTI=$((GUASTI+1))
done
if [ "$GUASTI" -gt 0 ]; then
  echo "ATTENZIONE: $GUASTI programmi non hanno risposto al controllo."
  echo "Non e' detto che dipenda da questa modifica, ma controlla."
fi

echo
echo "FATTO. Adesso manca il nome nel DNS di Cloudflare, una volta sola."
echo "ATTENZIONE: quel comando va dato SENZA sudo, come utente piero."
echo "Il certificato che autorizza le modifiche al DNS sta in"
echo "~/.cloudflared/cert.pem, cioe' nella cartella di piero: con sudo"
echo "cloudflared lo cerca in quella di root, non lo trova e non fa niente."
echo
echo "   cloudflared tunnel route dns \\"
echo "     d153afeb-11c8-45b5-9b94-574e36fffa67 $NOME"
echo
echo "Poi l'indirizzo pubblico sara':  https://$NOME"
echo "Per tornare indietro in qualunque momento:"
echo "   sudo cp -p $COPIA $CFG && sudo systemctl restart cloudflared"
