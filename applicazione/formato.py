# formato.py -- come i dati si mostrano all'utente.
#
# In archivio: date ISO (aaaa-mm-gg), importi in centesimi interi.
# A schermo: date gg/mm/aaaa, importi "12,50 euro" con il simbolo.
# Qui dentro ci sono gli accenti veri, perche' questi testi li legge l'utente.

from datetime import date, datetime

GIORNI = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato",
          "domenica")
MESI = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre")


def data_italiana(iso):
    """2026-11-15 -> 15/11/2026. Se il valore manca, stringa vuota."""
    if not iso:
        return ""
    try:
        return datetime.strptime(str(iso)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return str(iso)


def data_distesa(iso):
    """2026-11-15 -> «domenica 15 novembre 2026»."""
    if not iso:
        return ""
    try:
        giorno = datetime.strptime(str(iso)[:10], "%Y-%m-%d").date()
    except ValueError:
        return str(iso)
    return "%s %d %s %d" % (GIORNI[giorno.weekday()], giorno.day,
                            MESI[giorno.month - 1], giorno.year)


def data_ora_italiana(iso):
    """2026-11-15 18:30:00 -> 15/11/2026 alle 18:30."""
    if not iso:
        return ""
    try:
        quando = datetime.strptime(str(iso)[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return data_italiana(iso)
    return "%s alle %s" % (quando.strftime("%d/%m/%Y"), quando.strftime("%H:%M"))


def oggi_iso():
    return date.today().strftime("%Y-%m-%d")


def euro(centesimi):
    """1250 -> «12,50 €». Zero diventa «gratuito»."""
    if not centesimi:
        return "gratuito"
    intero, decimali = divmod(int(centesimi), 100)
    migliaia = "{:,}".format(intero).replace(",", ".")
    return "%s,%02d €" % (migliaia, decimali)


def euro_secco(centesimi):
    """Come euro(), ma lo zero resta «0,00 €» (serve nei totali)."""
    intero, decimali = divmod(int(centesimi or 0), 100)
    migliaia = "{:,}".format(intero).replace(",", ".")
    return "%s,%02d €" % (migliaia, decimali)


def persone(quante):
    """1 -> «1 persona», 4 -> «4 persone»."""
    quante = int(quante or 0)
    return "1 persona" if quante == 1 else "%d persone" % quante


def registra_filtri(app):
    """Rende questi aiuti utilizzabili dentro i template."""
    app.jinja_env.filters["data_italiana"] = data_italiana
    app.jinja_env.filters["data_distesa"] = data_distesa
    app.jinja_env.filters["data_ora_italiana"] = data_ora_italiana
    app.jinja_env.filters["euro"] = euro
    app.jinja_env.filters["euro_secco"] = euro_secco
    app.jinja_env.filters["persone"] = persone
