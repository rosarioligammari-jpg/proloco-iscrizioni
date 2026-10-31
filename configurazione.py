# configurazione.py -- tutte le impostazioni del programma in un unico punto.
#
# Programma: Iscrizioni Pro Loco Villafrati APS (manifestazioni ed eventi).
#
# Ogni impostazione si puo' cambiare da fuori con una variabile d'ambiente,
# come fanno gli altri programmi dello studio sul server: cosi' lo stesso
# codice gira sul PC di Windows e dentro il contenitore, senza modifiche.
#
# ATTENZIONE: il nome utente di Windows contiene uno spazio, percio' i
# percorsi si costruiscono solo con pathlib, mai incollando stringhe.

import os
from pathlib import Path


def _testo(nome, predefinito):
    valore = os.environ.get(nome, "").strip()
    return valore or predefinito


def _numero(nome, predefinito):
    valore = os.environ.get(nome, "").strip()
    try:
        return int(valore) if valore else predefinito
    except ValueError:
        return predefinito


def _acceso(nome, predefinito):
    """«1», «si», «true», «on» accendono; tutto il resto spegne."""
    valore = os.environ.get(nome, "").strip().lower()
    if not valore:
        return predefinito
    return valore in ("1", "si", "sì", "true", "vero", "on", "yes")


# ---------------------------------------------------------------- identita'

ENTE = _testo("ISCRIZIONI_ENTE", "Pro Loco Villafrati APS")
NOME_PROGRAMMA = "%s · Iscrizioni" % ENTE
TITOLO_SCHEDA = "Iscrizioni · %s" % ENTE

# Il logo si mette nella cartella applicazione/static/ con uno di questi
# nomi. Il primo che si trova e' quello che viene mostrato in testata.
# Se non c'e' nessun file, le pagine escono con la sola intestazione
# di testo: il programma non si ferma per il logo mancante.
NOMI_FILE_LOGO = ("logo.png", "logo.svg", "logo.jpg", "logo.jpeg",
                  "logo.webp")

# ------------------------------------------------------------------- rete

# Porte gia' impegnate da altri programmi dello studio:
#   sul PC di Windows: 5001 (ELMO), 5011 (DVR), 5012 (PSC), 5013 (POS);
#   sul server:        8100-8112 e 8120 (reali), 8200-8212 (prova).
# Questo programma usa la 5021 in locale, e sul server la 8113 (copia di
# prova: 8213), che arriva dalla variabile d'ambiente.
# Se la porta risulta occupata il programma lo dice e si ferma: la porta
# non si cambia da soli.
PORTA = _numero("ISCRIZIONI_PORTA", 5021)
INDIRIZZO = _testo("ISCRIZIONI_INDIRIZZO", "0.0.0.0")

# ---------------------------------------------------------------- percorsi

BASE = Path(__file__).resolve().parent
CARTELLA_DATI = Path(_testo("ISCRIZIONI_CARTELLA_DATI", str(BASE / "dati")))
CARTELLA_DATI_PROVA = BASE / "dati_prova"
NOME_DATABASE = "iscrizioni.sqlite"
NOME_FILE_CHIAVE = "chiave_segreta.txt"

# ------------------------------------------------------------- comportamento

# Numero massimo di persone che un capogruppo puo' iscrivere in una volta.
MASSIMO_PERSONE_PER_GRUPPO = _numero("ISCRIZIONI_MASSIMO_GRUPPO", 60)

# Lunghezza del codice di conferma mostrato all'iscritto.
LUNGHEZZA_CODICE_CONFERMA = 8

# ------------------------------------------- pubblicazione su internet

# Da accendere SOLTANTO quando il programma sta su internet dietro un
# collegamento sicuro (indirizzo che comincia con https). Serve a far
# viaggiare il cookie dell'area riservata solo cifrato. Se la si accende
# mentre si lavora in locale (http), l'area riservata non fa piu' entrare.
COLLEGAMENTO_SICURO = _acceso("ISCRIZIONI_COOKIE_SICURO", False)

# Il programma sta dietro un servizio che gli gira davanti (tunnel, proxy)?
# Serve a far capire al programma qual e' l'indirizzo vero di chi si
# collega e l'indirizzo pubblico da scrivere nei link.
DIETRO_UN_PROXY = _acceso("ISCRIZIONI_DIETRO_PROXY", False)

# Quante iscrizioni puo' inviare lo stesso collegamento in un minuto.
#
# ATTENZIONE al numero: molte persone diverse possono presentarsi con lo
# STESSO indirizzo (una famiglia sulla stessa rete di casa, oppure decine
# di utenti dello stesso gestore telefonico). Un numero basso bloccherebbe
# gente in buona fede appena il link gira nei gruppi. Venti al minuto
# ferma i programmi automatici senza dare fastidio alle persone: contro
# quelli la difesa vera e' il campo-trappola nel modulo.
INVII_AL_MINUTO = _numero("ISCRIZIONI_INVII_AL_MINUTO", 20)

# Dimensione massima di un invio. Oltre, la richiesta viene rifiutata.
DIMENSIONE_MASSIMA_INVIO = _numero("ISCRIZIONI_DIMENSIONE_MASSIMA",
                                   512 * 1024)
