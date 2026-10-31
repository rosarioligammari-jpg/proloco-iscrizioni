# avvia.py -- avvio del programma «Iscrizioni Pro Loco».
#
# Si lancia con:   python avvia.py
# oppure con il doppio clic su «Avvia Iscrizioni.bat» (Windows)
# o su «Avvia Iscrizioni.command» (Mac).

import socket
import sys
from pathlib import Path

# La cartella del programma deve stare nei percorsi di ricerca, altrimenti
# «import configurazione» non funziona quando si lancia da un'altra cartella.
BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from configurazione import INDIRIZZO, NOME_PROGRAMMA, PORTA  # noqa: E402
from applicazione import crea_applicazione  # noqa: E402


def porta_occupata(porta):
    """Controlla se la porta e' gia' in uso. La porta non si cambia da
    soli: se e' occupata si avvisa e si esce."""
    prova = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    prova.settimeout(0.5)
    try:
        return prova.connect_ex(("127.0.0.1", porta)) == 0
    finally:
        prova.close()


def indirizzi_locali():
    """Indirizzi da cui il programma risulta raggiungibile, per poterli
    scrivere a schermo (serve per provarlo dal telefono in rete locale)."""
    indirizzi = ["http://127.0.0.1:%d" % PORTA]
    try:
        presa = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            presa.connect(("8.8.8.8", 80))
            locale = presa.getsockname()[0]
        finally:
            presa.close()
        if locale and not locale.startswith("127."):
            indirizzi.append("http://%s:%d" % (locale, PORTA))
    except OSError:
        pass
    return indirizzi


def principale():
    print("")
    print("  %s" % NOME_PROGRAMMA)
    print("  " + "-" * len(NOME_PROGRAMMA))

    if porta_occupata(PORTA):
        print("")
        print("  ATTENZIONE: la porta %d risulta gia' occupata." % PORTA)
        print("  Forse il programma e' gia' avviato in un'altra finestra.")
        print("  Chiudi quella finestra e riprova. La porta non va cambiata")
        print("  da sola: se serve cambiarla, dirlo prima.")
        print("")
        input("  Premi Invio per chiudere...")
        return 1

    app = crea_applicazione()

    print("")
    print("  Il programma e' in funzione. Apri il browser su:")
    for indirizzo in indirizzi_locali():
        print("     %s" % indirizzo)
    print("")
    print("  Per fermarlo: chiudi questa finestra, oppure premi Ctrl+C.")
    print("")

    # Due server possibili. «waitress» e' quello buono: puro Python, uguale
    # su Windows, Mac e Linux, e adatto a stare su internet. Se non c'e',
    # si usa quello di prova di Flask, che va bene solo in locale.
    try:
        from waitress import serve
    except ImportError:
        serve = None

    if serve is None:
        print("  NOTA: sto usando il server di prova di Flask.")
        print("  Va bene per lavorare su questo computer, ma NON va messo")
        print("  su internet. Per installare quello buono:")
        print("     pip install waitress")
        print("")
        app.run(host=INDIRIZZO, port=PORTA, debug=False, threaded=True)
    else:
        serve(app, host=INDIRIZZO, port=PORTA, threads=8,
              ident="Iscrizioni")
    return 0


if __name__ == "__main__":
    sys.exit(principale())
