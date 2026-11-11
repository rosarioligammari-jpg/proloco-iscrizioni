# avvisi.py -- gli avvisi che arrivano sul telefono, con ntfy.
#
# Come funziona, in parole semplici: sul telefono si installa l'app
# «ntfy» e ci si iscrive a un CANALE, cioe' un nome segreto. Il programma,
# ogni volta che serve, manda un messaggio a quel canale e il telefono
# squilla. Niente account, niente password, niente app da pubblicare.
#
# DUE REGOLE, e sono il motivo per cui questo file e' fatto cosi'.
#
#   1. NESSUN NOME ESCE DA QUI. Chi si iscrive firma un'informativa che
#      dice che i suoi dati non vengono comunicati a terzi: se mandassimo
#      nome e telefono a ntfy, quella frase non sarebbe piu' vera.
#      L'avviso dice QUANTE persone e SU COSA, mai CHI. I nomi restano
#      sul server, dietro la password dell'area riservata, a un tocco di
#      distanza dal collegamento dentro l'avviso.
#   2. SE L'AVVISO NON PARTE, L'ISCRIZIONE RESTA. E' un di piu' per gli
#      organizzatori, non una condizione per iscriversi.

import json
import secrets
import threading
import traceback
import urllib.error
import urllib.request

SERVER_PREDEFINITO = "https://ntfy.sh"
CHIAVE_SERVER = "ntfy_server"
CHIAVE_CANALE = "ntfy_canale"


class AvvisoSpento(Exception):
    """Non si puo' mandare l'avviso, e si sa perche'."""


def canale_nuovo():
    """Propone un nome di canale difficile da indovinare.

    Il canale e' l'unica cosa che protegge gli avvisi: chi lo conosce li
    riceve. Per questo non si usa «proloco» o «iscrizioni», ma un nome
    con dentro una parte casuale.
    """
    return "iscrizioni-%s" % secrets.token_urlsafe(12).replace("-", "").lower()


def indirizzo_canale(server, canale):
    return "%s/%s" % ((server or SERVER_PREDEFINITO).rstrip("/"), canale)


def manda(server, canale, titolo, messaggio, collegamento=None,
          priorita=3, etichette=None, attesa=10):
    """Manda l'avviso. Alza AvvisoSpento se non si puo'."""
    canale = (canale or "").strip()
    if not canale:
        raise AvvisoSpento("Nessun canale impostato: non mando niente.")

    server = (server or SERVER_PREDEFINITO).rstrip("/")
    corpo = {
        "topic": canale,
        "title": titolo,
        "message": messaggio,
        "priority": priorita,
    }
    if collegamento:
        corpo["click"] = collegamento
    if etichette:
        corpo["tags"] = list(etichette)

    # Si manda in formato JSON e non come testo semplice: cosi' gli
    # accenti nel titolo arrivano giusti.
    dati = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
    richiesta = urllib.request.Request(
        server, data=dati, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(richiesta, timeout=attesa) as risposta:
            if risposta.status >= 300:
                raise AvvisoSpento("Il servizio ha risposto %d"
                                   % risposta.status)
    except urllib.error.HTTPError as errore:
        raise AvvisoSpento("Il servizio ha risposto %d (%s)"
                           % (errore.code, errore.reason))
    except urllib.error.URLError as errore:
        raise AvvisoSpento("Non sono riuscito a raggiungere %s: %s"
                           % (server, errore.reason))
    except OSError as errore:
        raise AvvisoSpento("Non sono riuscito a raggiungere %s: %s"
                           % (server, errore))


def manda_senza_far_danni(server, canale, titolo, messaggio,
                          collegamento=None, etichette=None):
    """Manda in una finestra a parte: qualunque guaio NON tocca chi si
    sta iscrivendo. Il motivo finisce nei registri del programma."""
    def lavoro():
        try:
            manda(server, canale, titolo, messaggio, collegamento,
                  etichette=etichette)
            print("  [avviso] mandato al canale %s" % canale)
        except AvvisoSpento as motivo:
            print("  [avviso] NON mandato: %s" % motivo)
        except Exception:
            print("  [avviso] NON mandato, errore imprevisto:")
            traceback.print_exc()

    threading.Thread(target=lavoro, daemon=True).start()
