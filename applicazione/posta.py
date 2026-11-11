# posta.py -- l'invio degli avvisi agli organizzatori.
#
# Usa la casella unica dei programmi dello studio, quella descritta in
# /srv/app-dati/posta.conf (dentro il contenitore si vede come /posta.conf).
# E' lo stesso meccanismo di Gestione Mezzi e degli altri: una casella
# sola, un file solo, scritto da ~/metti-password-posta.sh.
#
# Due regole, e sono quelle che contano:
#
#   1. SE LA POSTA NON PARTE, L'ISCRIZIONE RESTA. L'avviso e' un di piu'
#      per gli organizzatori: non deve mai far fallire l'iscrizione di una
#      persona. Qualunque guaio qui dentro viene catturato e scritto nella
#      finestra del programma, e chi si iscrive non se ne accorge.
#   2. Se il file della casella non c'e', non si prova nemmeno: si dice e
#      si smette. Meglio un errore chiaro che venti messaggi non partiti
#      di cui nessuno si accorge.

import os
import smtplib
import ssl
import threading
import traceback
from email.message import EmailMessage
from email.utils import formataddr

FILE_POSTA = os.environ.get("ISCRIZIONI_POSTA", "/posta.conf")
NOME_MITTENTE = "Iscrizioni Pro Loco"


class PostaSpenta(Exception):
    """Non si puo' spedire, e si sa perche'."""


def impostazioni(percorso=None):
    """Legge il file della casella.

    Il formato e' quello gia' in uso sul server: una riga per voce,
    «chiave valore» separati da uno spazio, righe vuote e righe che
    cominciano con # ignorate.
    """
    percorso = percorso or FILE_POSTA
    if not os.path.exists(percorso):
        raise PostaSpenta(
            "Non trovo il file della casella (%s): gli avvisi non partono. "
            "Si scrive con ~/metti-password-posta.sh sul server." % percorso)

    valori = {}
    with open(percorso, encoding="utf-8") as file_aperto:
        for riga in file_aperto:
            riga = riga.strip()
            if not riga or riga.startswith("#"):
                continue
            pezzi = riga.split(None, 1)
            if len(pezzi) == 2:
                valori[pezzi[0].lower()] = pezzi[1].strip()

    for chiave in ("server", "porta", "casella", "password"):
        if not valori.get(chiave):
            raise PostaSpenta(
                "Nel file della casella manca «%s»: gli avvisi non partono."
                % chiave)
    return valori


def indirizzi(testo):
    """«uno@x.it, due@y.it» -> ['uno@x.it', 'due@y.it'].

    Si accettano virgole, punti e virgola e a capo: chi scrive nel modulo
    non deve stare a pensare al separatore giusto.
    """
    if not testo:
        return []
    pulito = testo.replace(";", ",").replace("\n", ",").replace(" ", ",")
    return [pezzo.strip() for pezzo in pulito.split(",")
            if pezzo.strip() and "@" in pezzo]


def spedisci(destinatari, oggetto, testo, percorso=None):
    """Spedisce davvero. Alza PostaSpenta se non si puo'."""
    destinatari = [d for d in destinatari if d]
    if not destinatari:
        raise PostaSpenta("Nessun destinatario: non spedisco niente.")

    conf = impostazioni(percorso)
    messaggio = EmailMessage()
    messaggio["From"] = formataddr((NOME_MITTENTE, conf["casella"]))
    messaggio["To"] = ", ".join(destinatari)
    if conf.get("rispondi_a"):
        messaggio["Reply-To"] = conf["rispondi_a"]
    messaggio["Subject"] = oggetto
    messaggio.set_content(testo)

    contesto = ssl.create_default_context()
    porta = int(conf["porta"])
    if porta == 465:
        with smtplib.SMTP_SSL(conf["server"], porta, context=contesto,
                              timeout=20) as sessione:
            sessione.login(conf["casella"], conf["password"])
            sessione.send_message(messaggio)
    else:
        with smtplib.SMTP(conf["server"], porta, timeout=20) as sessione:
            sessione.starttls(context=contesto)
            sessione.login(conf["casella"], conf["password"])
            sessione.send_message(messaggio)


def spedisci_senza_far_danni(destinatari, oggetto, testo, percorso=None):
    """Spedisce in una finestra a parte, e qualunque cosa vada storta NON
    tocca chi si sta iscrivendo.

    Chi compila il modulo non deve aspettare il server della posta, e non
    deve vedere un errore se la posta e' giu'. L'organizzatore lo trova
    scritto nella finestra del programma.
    """
    def lavoro():
        try:
            spedisci(destinatari, oggetto, testo, percorso)
            print("  [posta] avviso spedito a %s" % ", ".join(destinatari))
        except PostaSpenta as motivo:
            print("  [posta] avviso NON spedito: %s" % motivo)
        except Exception:
            print("  [posta] avviso NON spedito, errore imprevisto:")
            traceback.print_exc()

    threading.Thread(target=lavoro, daemon=True).start()
