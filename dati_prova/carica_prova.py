# carica_prova.py -- carica una manifestazione DI PROVA nel database.
#
# ATTENZIONE: i nomi delle attivita', i posti e le quote qui sotto sono
# INVENTATI, serviranno solo a far vedere come funziona il programma.
# Vanno sostituiti con quelli veri del Motor Village Fest.
#
# Si lancia dalla cartella del programma con:
#     python "dati_prova\carica_prova.py"
#
# Se la manifestazione esiste gia', il programma non tocca nulla e lo dice:
# niente cancellazioni a sorpresa.

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from applicazione import archivio  # noqa: E402

CODICE = "motor-village-fest"

MANIFESTAZIONE = {
    "codice": CODICE,
    "nome": "Motor Village Fest",
    "sottotitolo": "Raduno di auto e moto, giro turistico e festa in piazza",
    "descrizione": (
        "Due giorni di motori, strade e tavolate.\n"
        "Le iscrizioni servono a sapere quanti saremo e a non lasciare "
        "nessuno a piedi: per il pranzo, per la gimkana e per il giro "
        "turistico i posti sono contati.\n"
        "Chi arriva in gruppo può iscrivere tutti con una sola iscrizione."
    ),
    "luogo": "Villafrati (PA)",
    "data_inizio": "2026-11-14",
    "data_fine": "2026-11-15",
    "organizzatore": "Pro Loco Villafrati APS",
    "contatto_organizzatore": "Pro Loco Villafrati APS · telefono 000 0000000",
    "informativa_privacy": (
        "I dati che lasci (nome, cognome, telefono, eventuale email e i "
        "nomi dei partecipanti del gruppo) sono raccolti dalla Pro Loco "
        "Villafrati APS al solo scopo di organizzare questa "
        "manifestazione: contare i partecipanti, gestire i posti delle "
        "singole attività e avvisarti se qualcosa cambia.\n"
        "I dati non vengono comunicati a terzi né usati per altri scopi, "
        "e vengono cancellati entro sei mesi dalla fine della "
        "manifestazione.\n"
        "Puoi chiedere in qualunque momento di vedere, correggere o "
        "cancellare i tuoi dati scrivendo agli organizzatori ai contatti "
        "indicati in questa pagina."
    ),
    "iscrizioni_aperte": 1,
    "chiusura_iscrizioni": "2026-11-10",
    "lista_attesa": 1,
}

# nome, descrizione, giorno, ora, posti (None = senza limite), quota in centesimi
ATTIVITA = [
    ("Raduno e accoglienza equipaggi",
     "Ritrovo in piazza, consegna del numero e caffè di benvenuto.",
     "2026-11-14", "08:30", 120, 0),
    ("Giro turistico (circa 60 km)",
     "Percorso su strade panoramiche con sosta fotografica. "
     "Casco e documenti del veicolo obbligatori.",
     "2026-11-14", "10:00", 80, 500),
    ("Pranzo sociale",
     "Menù unico. Segnala nelle note eventuali allergie o menù per bambini.",
     "2026-11-14", "13:00", 150, 2000),
    ("Gimkana a tempo",
     "Prova di abilità su percorso chiuso, a batterie.",
     "2026-11-14", "16:00", 40, 1000),
    ("Esposizione veicoli storici",
     "Spazio riservato ai veicoli di oltre trent'anni.",
     "2026-11-15", "09:00", 50, 0),
    ("Prova minimoto per ragazzi",
     "Riservata ai ragazzi dagli 8 ai 14 anni, con istruttore. "
     "Serve l'autorizzazione di un genitore il giorno della prova.",
     "2026-11-15", "10:30", 25, 0),
    ("Visita guidata al centro storico",
     "Per accompagnatori e famiglie. Nessun limite di posti.",
     "2026-11-15", "11:00", None, 0),
    ("Cena e premiazione",
     "Premiazione degli equipaggi e cena in piazza.",
     "2026-11-15", "19:30", 150, 2500),
]


def carica():
    archivio.prepara()
    con = archivio.connessione()
    try:
        if archivio.manifestazione_per_codice(con, CODICE) is not None:
            print("")
            print("  La manifestazione di prova c'e' gia' in archivio.")
            print("  Non tocco niente. Se vuoi ricaricarla da zero, prima")
            print("  fai una copia del file dati\\iscrizioni.sqlite e poi")
            print("  cancellala dall'area riservata.")
            print("")
            return 0

        campi = list(MANIFESTAZIONE.keys())
        valori = [MANIFESTAZIONE[c] for c in campi]
        campi.append("creata_il")
        valori.append(archivio.adesso())
        con.execute(
            "INSERT INTO manifestazione (%s) VALUES (%s)"
            % (", ".join(campi), ", ".join("?" * len(campi))), valori)
        manifestazione_id = con.execute(
            "SELECT id FROM manifestazione WHERE codice = ?",
            (CODICE,)).fetchone()["id"]

        for ordine, voce in enumerate(ATTIVITA, start=1):
            nome, descrizione, giorno, ora, posti, quota = voce
            con.execute(
                "INSERT INTO attivita (manifestazione_id, nome, descrizione, "
                "  giorno, ora_inizio, posti, quota_centesimi, ordine, attiva) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
                (manifestazione_id, nome, descrizione, giorno, ora, posti,
                 quota, ordine))

        print("")
        print("  Caricata la manifestazione di PROVA «Motor Village Fest»")
        print("  con %d attivita'." % len(ATTIVITA))
        print("  Indirizzo della pagina di iscrizione:")
        print("     http://127.0.0.1:5021/m/%s" % CODICE)
        print("")
        print("  Ricorda: nomi, posti e quote sono inventati, da sostituire.")
        print("")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(carica())
