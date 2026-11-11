# riservato.py -- l'area dell'organizzatore, protetta da password.
#
# Qui dentro si fa tutto quello che il pubblico non deve vedere: creare le
# manifestazioni e le attivita', guardare gli iscritti, i totali, chiudere
# le iscrizioni, scaricare l'elenco.
#
# Due regole che valgono in tutta questa parte:
#   - NIENTE si cancella davvero. Un'iscrizione sbagliata si ANNULLA e
#     resta negli archivi; un'attivita' che non si fa piu' si SPEGNE.
#   - dopo ogni salvataggio si dice all'utente CHE COSA e' stato salvato.

import csv
import io
import re
from datetime import datetime
from functools import wraps

from flask import (Blueprint, Response, abort, flash, g, redirect,
                   render_template, request, session, url_for)

from configurazione import ENTE
from applicazione import archivio, avvisi
from applicazione.formato import oggi_iso

riservato = Blueprint("riservato", __name__, url_prefix="/riservato")

CHIAVE_PASSWORD = "password_area_riservata"

# Tentativi sbagliati: si tiene il conto in memoria, si azzera al riavvio.
# Non e' una cassaforte, e' un freno contro chi prova le password a macchina.
_TENTATIVI = {"quanti": 0, "fino_a": None}
MASSIMO_TENTATIVI = 5
MINUTI_DI_BLOCCO = 10


# --------------------------------------------------------------- ingresso

def serve_entrata(funzione):
    """Mette il lucchetto a una pagina: senza password non si passa."""
    @wraps(funzione)
    def controlla(*argomenti, **parole):
        if not session.get("riservato"):
            return redirect(url_for("riservato.entrata", torna_a=request.path))
        return funzione(*argomenti, **parole)
    return controlla


def _bloccato():
    fino_a = _TENTATIVI["fino_a"]
    if fino_a and datetime.now() < fino_a:
        return int((fino_a - datetime.now()).total_seconds() // 60) + 1
    return 0


@riservato.route("/entrata", methods=["GET", "POST"])
def entrata():
    conservata = archivio.impostazione(g.con, CHIAVE_PASSWORD)
    prima_volta = not conservata

    if request.method == "POST":
        if prima_volta:
            password = request.form.get("password", "")
            ripetuta = request.form.get("ripetuta", "")
            if len(password) < 8:
                flash("La password deve essere lunga almeno 8 caratteri.",
                      "errore")
            elif password != ripetuta:
                flash("Le due password scritte non coincidono.", "errore")
            else:
                archivio.scrivi_impostazione(g.con, CHIAVE_PASSWORD,
                                             archivio.cifra_password(password))
                session["riservato"] = True
                flash("Password impostata. Da adesso serve per entrare qui.",
                      "fatto")
                return redirect(url_for("riservato.elenco"))
        else:
            minuti = _bloccato()
            if minuti:
                flash("Troppi tentativi sbagliati. Riprova fra %d minuti."
                      % minuti, "errore")
            elif archivio.password_corretta(request.form.get("password", ""),
                                            conservata):
                _TENTATIVI["quanti"] = 0
                _TENTATIVI["fino_a"] = None
                session["riservato"] = True
                destinazione = request.form.get("torna_a") or ""
                if destinazione.startswith("/riservato"):
                    return redirect(destinazione)
                return redirect(url_for("riservato.elenco"))
            else:
                _TENTATIVI["quanti"] += 1
                if _TENTATIVI["quanti"] >= MASSIMO_TENTATIVI:
                    from datetime import timedelta
                    _TENTATIVI["fino_a"] = (datetime.now()
                                            + timedelta(minutes=MINUTI_DI_BLOCCO))
                    _TENTATIVI["quanti"] = 0
                    flash("Troppi tentativi sbagliati: aspetta %d minuti."
                          % MINUTI_DI_BLOCCO, "errore")
                else:
                    flash("Password sbagliata.", "errore")

    return render_template("riservato/entrata.html", prima_volta=prima_volta,
                           torna_a=request.args.get("torna_a", ""))


@riservato.route("/uscita", methods=["POST"])
def uscita():
    session.pop("riservato", None)
    flash("Sei uscito dall'area riservata.", "fatto")
    return redirect(url_for("riservato.entrata"))


# ------------------------------------------------------------ conversioni

def _data_da_modulo(valore):
    """Il campo data del browser manda gia' aaaa-mm-gg. Si accetta anche
    gg/mm/aaaa, per chi scrive a mano."""
    valore = (valore or "").strip()
    if not valore:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", valore):
        return valore
    pezzi = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$", valore)
    if pezzi:
        giorno, mese, anno = pezzi.groups()
        return "%s-%02d-%02d" % (anno, int(mese), int(giorno))
    return None


def _centesimi_da_modulo(valore):
    """«20», «20,00», «20.5», «€ 20,00» -> centesimi interi."""
    valore = (valore or "").strip().replace("€", "").replace(" ", "")
    if not valore:
        return 0
    valore = valore.replace(",", ".")
    try:
        return int(round(float(valore) * 100))
    except ValueError:
        return 0


def _posti_da_modulo(valore):
    """Vuoto o zero significa «nessun limite», non «zero posti»."""
    valore = (valore or "").strip()
    if not valore:
        return None
    try:
        quanti = int(valore)
    except ValueError:
        return None
    return quanti if quanti > 0 else None


def _codice_da_nome(con, nome, escluso=None):
    """Dal nome ricava il pezzo di indirizzo: «Motor Village Fest» diventa
    «motor-village-fest». Se e' gia' preso, aggiunge un numero."""
    base = re.sub(r"[^a-z0-9]+", "-",
                  (nome or "manifestazione").lower().strip()).strip("-")
    base = (base or "manifestazione")[:60]
    codice, contatore = base, 1
    while True:
        esistente = archivio.manifestazione_per_codice(con, codice)
        if esistente is None or esistente["id"] == escluso:
            return codice
        contatore += 1
        codice = "%s-%d" % (base, contatore)


# ------------------------------------------------------------- panoramica

@riservato.route("/")
@serve_entrata
def elenco():
    righe = archivio.manifestazioni(g.con)
    prospetto = []
    for m in righe:
        totali = archivio.totali_manifestazione(g.con, m["id"])
        prospetto.append({"m": m, "totali": totali})
    return render_template("riservato/elenco.html", manifestazioni=prospetto)


@riservato.route("/manifestazione/<int:numero>")
@serve_entrata
def manifestazione(numero):
    m = archivio.manifestazione_per_id(g.con, numero)
    if m is None:
        abort(404)
    return render_template(
        "riservato/manifestazione.html",
        m=m,
        attivita=archivio.prospetto_attivita_riservato(g.con, numero),
        # Anche le annullate: sono segnate in grigio con l'etichetta, e
        # senza mostrarle non si potrebbe ne' rimetterle fra le valide ne'
        # cancellarle.
        iscrizioni=archivio.prospetto_iscrizioni(g.con, numero,
                                                 includi_annullate=True),
        totali=archivio.totali_manifestazione(g.con, numero),
        indirizzo_pubblico=url_for("pubblico.manifestazione",
                                   codice=m["codice"], _external=True))


# --------------------------------------------- avvisi sul telefono (ntfy)

@riservato.route("/avvisi", methods=["GET", "POST"])
@serve_entrata
def avvisi_telefono():
    """Dove si dice a quale canale mandare gli avvisi sul telefono.

    È un'impostazione sola per tutto il programma, non per singola
    manifestazione: il telefono che deve squillare è sempre quello.
    """
    canale = archivio.impostazione(g.con, avvisi.CHIAVE_CANALE, "")
    server = archivio.impostazione(g.con, avvisi.CHIAVE_SERVER,
                                   avvisi.SERVER_PREDEFINITO)

    if request.method == "POST":
        if request.form.get("azione") == "prova":
            if not canale:
                flash("Prima salva il canale, poi si può fare la prova.",
                      "errore")
            else:
                try:
                    avvisi.manda(
                        server, canale, "Prova degli avvisi",
                        "Se leggi questo messaggio sul telefono, gli avvisi "
                        "funzionano.",
                        collegamento=url_for("riservato.elenco",
                                             _external=True),
                        etichette=["white_check_mark"])
                    flash("Avviso di prova mandato. Deve comparire sul "
                          "telefono entro pochi secondi.", "fatto")
                except avvisi.AvvisoSpento as motivo:
                    flash("Non sono riuscito a mandarlo: %s" % motivo,
                          "errore")
            return redirect(url_for("riservato.avvisi_telefono"))

        nuovo_canale = request.form.get("canale", "").strip()
        nuovo_server = (request.form.get("server", "").strip()
                        or avvisi.SERVER_PREDEFINITO)
        if nuovo_canale and not re.match(r"^[A-Za-z0-9_-]{6,64}$",
                                         nuovo_canale):
            flash("Il nome del canale può avere solo lettere, numeri, "
                  "trattini e trattini bassi, da 6 a 64 caratteri.", "errore")
        elif not nuovo_server.startswith(("http://", "https://")):
            flash("L'indirizzo del servizio deve cominciare con https://",
                  "errore")
        else:
            archivio.scrivi_impostazione(g.con, avvisi.CHIAVE_CANALE,
                                         nuovo_canale)
            archivio.scrivi_impostazione(g.con, avvisi.CHIAVE_SERVER,
                                         nuovo_server)
            if nuovo_canale:
                flash("Salvato. Gli avvisi andranno al canale «%s»."
                      % nuovo_canale, "fatto")
            else:
                flash("Salvato: nessun avviso sul telefono.", "fatto")
            return redirect(url_for("riservato.avvisi_telefono"))

    return render_template(
        "riservato/avvisi.html",
        canale=canale,
        proposta=avvisi.canale_nuovo(),
        server=server,
        server_predefinito=avvisi.SERVER_PREDEFINITO,
        indirizzo=(avvisi.indirizzo_canale(server, canale)
                   if canale else ""))


# ------------------------------------------------- creare e modificare

@riservato.route("/manifestazione/nuova", methods=["GET", "POST"])
@serve_entrata
def nuova_manifestazione():
    if request.method == "POST":
        valori = _valori_manifestazione()
        errori = _controlla_manifestazione(valori)
        if errori:
            return render_template("riservato/modifica_manifestazione.html",
                                   m=None, valori=valori, errori=errori), 400
        codice = _codice_da_nome(g.con, valori["nome"])
        g.con.execute(
            "INSERT INTO manifestazione (codice, nome, sottotitolo, "
            "  descrizione, luogo, data_inizio, data_fine, organizzatore, "
            "  contatto_organizzatore, informativa_privacy, "
            "  iscrizioni_aperte, chiusura_iscrizioni, lista_attesa, "
            "  avvisi_a, creata_il) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (codice, valori["nome"], valori["sottotitolo"],
             valori["descrizione"], valori["luogo"], valori["data_inizio"],
             valori["data_fine"], valori["organizzatore"],
             valori["contatto_organizzatore"], valori["informativa_privacy"],
             1 if valori["iscrizioni_aperte"] else 0,
             valori["chiusura_iscrizioni"],
             1 if valori["lista_attesa"] else 0, valori["avvisi_a"],
             archivio.adesso()))
        nuova = archivio.manifestazione_per_codice(g.con, codice)
        flash("Creata la manifestazione «%s». Adesso aggiungi le attività."
              % valori["nome"], "fatto")
        return redirect(url_for("riservato.manifestazione", numero=nuova["id"]))

    return render_template("riservato/modifica_manifestazione.html",
                           m=None, valori=_valori_vuoti(), errori=[])


@riservato.route("/manifestazione/<int:numero>/modifica",
                 methods=["GET", "POST"])
@serve_entrata
def modifica_manifestazione(numero):
    m = archivio.manifestazione_per_id(g.con, numero)
    if m is None:
        abort(404)

    if request.method == "POST":
        valori = _valori_manifestazione()
        errori = _controlla_manifestazione(valori)
        if errori:
            return render_template("riservato/modifica_manifestazione.html",
                                   m=m, valori=valori, errori=errori), 400
        g.con.execute(
            "UPDATE manifestazione SET nome = ?, sottotitolo = ?, "
            "  descrizione = ?, luogo = ?, data_inizio = ?, data_fine = ?, "
            "  organizzatore = ?, contatto_organizzatore = ?, "
            "  informativa_privacy = ?, iscrizioni_aperte = ?, "
            "  chiusura_iscrizioni = ?, lista_attesa = ?, "
            "  avvisi_a = ? WHERE id = ?",
            (valori["nome"], valori["sottotitolo"], valori["descrizione"],
             valori["luogo"], valori["data_inizio"], valori["data_fine"],
             valori["organizzatore"], valori["contatto_organizzatore"],
             valori["informativa_privacy"],
             1 if valori["iscrizioni_aperte"] else 0,
             valori["chiusura_iscrizioni"],
             1 if valori["lista_attesa"] else 0, valori["avvisi_a"],
             numero))
        flash("Salvato: «%s»." % valori["nome"], "fatto")
        return redirect(url_for("riservato.manifestazione", numero=numero))

    return render_template("riservato/modifica_manifestazione.html",
                           m=m, valori=_valori_da_riga(m), errori=[])


def informativa_predefinita():
    """Un'informativa gia' scritta per una manifestazione nuova.

    Non e' un parere legale: e' un punto di partenza onesto, che dice
    chi raccoglie i dati, per farne cosa, per quanto tempo e a chi
    rivolgersi. Va letta e adattata, non firmata a scatola chiusa.
    """
    return (
        "I dati che lasci (nome, cognome, telefono, eventuale email e i "
        "nomi dei partecipanti del gruppo) sono raccolti da %s al solo "
        "scopo di organizzare questa manifestazione: contare i "
        "partecipanti, gestire i posti delle singole attività e avvisarti "
        "se qualcosa cambia.\n"
        "I dati non vengono comunicati a terzi né usati per altri scopi, e "
        "vengono cancellati entro sei mesi dalla fine della "
        "manifestazione.\n"
        "Puoi chiedere in qualunque momento di vedere, correggere o "
        "cancellare i tuoi dati scrivendo agli organizzatori ai contatti "
        "indicati in questa pagina." % ENTE)


def _valori_vuoti():
    return {"nome": "", "sottotitolo": "", "descrizione": "", "luogo": "",
            "data_inizio": "", "data_fine": "", "organizzatore": ENTE,
            "contatto_organizzatore": "",
            "informativa_privacy": informativa_predefinita(),
            "iscrizioni_aperte": True, "chiusura_iscrizioni": "",
            "lista_attesa": True, "avvisi_a": ""}


def _valori_da_riga(m):
    return {"nome": m["nome"], "sottotitolo": m["sottotitolo"],
            "descrizione": m["descrizione"], "luogo": m["luogo"],
            "data_inizio": m["data_inizio"] or "",
            "data_fine": m["data_fine"] or "",
            "organizzatore": m["organizzatore"],
            "contatto_organizzatore": m["contatto_organizzatore"],
            "informativa_privacy": m["informativa_privacy"],
            "iscrizioni_aperte": bool(m["iscrizioni_aperte"]),
            "chiusura_iscrizioni": m["chiusura_iscrizioni"] or "",
            "lista_attesa": bool(m["lista_attesa"]),
            "avvisi_a": (m["avvisi_a"]
                         if "avvisi_a" in m.keys() else "")}


def _valori_manifestazione():
    moduli = request.form
    return {
        "nome": moduli.get("nome", "").strip(),
        "sottotitolo": moduli.get("sottotitolo", "").strip(),
        "descrizione": moduli.get("descrizione", "").strip(),
        "luogo": moduli.get("luogo", "").strip(),
        "data_inizio": _data_da_modulo(moduli.get("data_inizio")),
        "data_fine": _data_da_modulo(moduli.get("data_fine")),
        "organizzatore": moduli.get("organizzatore", "").strip(),
        "contatto_organizzatore": moduli.get("contatto_organizzatore",
                                             "").strip(),
        "informativa_privacy": moduli.get("informativa_privacy", "").strip(),
        "iscrizioni_aperte": bool(moduli.get("iscrizioni_aperte")),
        "chiusura_iscrizioni": _data_da_modulo(
            moduli.get("chiusura_iscrizioni")),
        "lista_attesa": bool(moduli.get("lista_attesa")),
        "avvisi_a": moduli.get("avvisi_a", "").strip(),
    }


def _controlla_manifestazione(valori):
    errori = []
    if not valori["nome"]:
        errori.append("Manca il nome della manifestazione.")
    if not valori["informativa_privacy"]:
        errori.append("Manca l'informativa privacy: senza quella il modulo "
                      "non si può pubblicare.")
    if (valori["data_inizio"] and valori["data_fine"]
            and valori["data_fine"] < valori["data_inizio"]):
        errori.append("La data di fine viene prima di quella di inizio.")
    return errori


# ------------------------------------------------------------- attivita'

@riservato.route("/manifestazione/<int:numero>/attivita/nuova",
                 methods=["GET", "POST"])
@serve_entrata
def nuova_attivita(numero):
    m = archivio.manifestazione_per_id(g.con, numero)
    if m is None:
        abort(404)

    if request.method == "POST":
        valori = _valori_attivita()
        if not valori["nome"]:
            return render_template("riservato/modifica_attivita.html", m=m,
                                   a=None, valori=valori,
                                   errori=["Manca il nome dell'attività."]), 400
        ultimo = g.con.execute(
            "SELECT COALESCE(MAX(ordine), 0) AS n FROM attivita "
            "WHERE manifestazione_id = ?", (numero,)).fetchone()["n"]
        g.con.execute(
            "INSERT INTO attivita (manifestazione_id, nome, descrizione, "
            "  giorno, ora_inizio, posti, quota_centesimi, ordine, attiva) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
            (numero, valori["nome"], valori["descrizione"], valori["giorno"],
             valori["ora_inizio"], valori["posti"], valori["quota_centesimi"],
             ultimo + 1))
        flash("Aggiunta l'attività «%s»." % valori["nome"], "fatto")
        return redirect(url_for("riservato.manifestazione", numero=numero))

    return render_template("riservato/modifica_attivita.html", m=m, a=None,
                           valori=_valori_attivita_vuoti(), errori=[])


@riservato.route("/attivita/<int:numero>/modifica", methods=["GET", "POST"])
@serve_entrata
def modifica_attivita(numero):
    a = archivio.attivita_per_id(g.con, numero)
    if a is None:
        abort(404)
    m = archivio.manifestazione_per_id(g.con, a["manifestazione_id"])

    if request.method == "POST":
        valori = _valori_attivita()
        errori = []
        if not valori["nome"]:
            errori.append("Manca il nome dell'attività.")
        occupati = archivio.persone_confermate_per_attivita(
            g.con, m["id"]).get(numero, 0)
        if valori["posti"] is not None and valori["posti"] < occupati:
            errori.append("Ci sono già %d persone iscritte: i posti non "
                          "possono scendere sotto questo numero. Per "
                          "chiudere l'attività usa «sospendi»." % occupati)
        if errori:
            return render_template("riservato/modifica_attivita.html", m=m,
                                   a=a, valori=valori, errori=errori), 400
        g.con.execute(
            "UPDATE attivita SET nome = ?, descrizione = ?, giorno = ?, "
            "  ora_inizio = ?, posti = ?, quota_centesimi = ? WHERE id = ?",
            (valori["nome"], valori["descrizione"], valori["giorno"],
             valori["ora_inizio"], valori["posti"], valori["quota_centesimi"],
             numero))
        flash("Salvato: attività «%s»." % valori["nome"], "fatto")
        return redirect(url_for("riservato.manifestazione", numero=m["id"]))

    return render_template("riservato/modifica_attivita.html", m=m, a=a,
                           valori=_valori_attivita_da_riga(a), errori=[])


def _valori_attivita_vuoti():
    return {"nome": "", "descrizione": "", "giorno": "", "ora_inizio": "",
            "posti": None, "posti_testo": "", "quota_centesimi": 0,
            "quota_testo": ""}


def _valori_attivita_da_riga(a):
    return {"nome": a["nome"], "descrizione": a["descrizione"],
            "giorno": a["giorno"] or "", "ora_inizio": a["ora_inizio"],
            "posti": a["posti"],
            "posti_testo": "" if a["posti"] is None else str(a["posti"]),
            "quota_centesimi": a["quota_centesimi"],
            "quota_testo": ("" if not a["quota_centesimi"]
                            else "%d,%02d" % divmod(a["quota_centesimi"], 100))}


def _valori_attivita():
    moduli = request.form
    return {
        "nome": moduli.get("nome", "").strip(),
        "descrizione": moduli.get("descrizione", "").strip(),
        "giorno": _data_da_modulo(moduli.get("giorno")),
        "ora_inizio": moduli.get("ora_inizio", "").strip(),
        "posti": _posti_da_modulo(moduli.get("posti")),
        "posti_testo": moduli.get("posti", "").strip(),
        "quota_centesimi": _centesimi_da_modulo(moduli.get("quota")),
        "quota_testo": moduli.get("quota", "").strip(),
    }


@riservato.route("/attivita/<int:numero>/sospendi", methods=["POST"])
@serve_entrata
def sospendi_attivita(numero):
    a = archivio.attivita_per_id(g.con, numero)
    if a is None:
        abort(404)
    nuovo_stato = 0 if a["attiva"] else 1
    g.con.execute("UPDATE attivita SET attiva = ? WHERE id = ?",
                  (nuovo_stato, numero))
    flash("L'attività «%s» adesso %s nel modulo di iscrizione."
          % (a["nome"], "compare" if nuovo_stato else "non compare più"),
          "fatto")
    return redirect(url_for("riservato.manifestazione",
                            numero=a["manifestazione_id"]))


# --------------------------------------------------- apertura e chiusura

@riservato.route("/manifestazione/<int:numero>/apertura", methods=["POST"])
@serve_entrata
def apertura(numero):
    m = archivio.manifestazione_per_id(g.con, numero)
    if m is None:
        abort(404)
    nuovo_stato = 0 if m["iscrizioni_aperte"] else 1
    g.con.execute("UPDATE manifestazione SET iscrizioni_aperte = ? "
                  "WHERE id = ?", (nuovo_stato, numero))
    flash("Iscrizioni %s per «%s»."
          % ("riaperte" if nuovo_stato else "chiuse", m["nome"]), "fatto")
    return redirect(url_for("riservato.manifestazione", numero=numero))


@riservato.route("/manifestazione/<int:numero>/duplica", methods=["POST"])
@serve_entrata
def duplica(numero):
    """Rifa' la stessa manifestazione per l'anno dopo: copia attivita',
    posti e quote, NON copia gli iscritti, e nasce a iscrizioni chiuse."""
    m = archivio.manifestazione_per_id(g.con, numero)
    if m is None:
        abort(404)
    nome = "%s (copia)" % m["nome"]
    codice = _codice_da_nome(g.con, nome)
    g.con.execute(
        "INSERT INTO manifestazione (codice, nome, sottotitolo, descrizione, "
        "  luogo, organizzatore, contatto_organizzatore, "
        "  informativa_privacy, iscrizioni_aperte, lista_attesa, "
        "  avvisi_a, creata_il) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)",
        (codice, nome, m["sottotitolo"], m["descrizione"], m["luogo"],
         m["organizzatore"], m["contatto_organizzatore"],
         m["informativa_privacy"], m["lista_attesa"],
         (m["avvisi_a"] if "avvisi_a" in m.keys() else ""),
         archivio.adesso()))
    copia = archivio.manifestazione_per_codice(g.con, codice)
    quante = 0
    for a in archivio.attivita_di(g.con, numero, solo_attive=False):
        g.con.execute(
            "INSERT INTO attivita (manifestazione_id, nome, descrizione, "
            "  ora_inizio, posti, quota_centesimi, ordine, attiva) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (copia["id"], a["nome"], a["descrizione"], a["ora_inizio"],
             a["posti"], a["quota_centesimi"], a["ordine"], a["attiva"]))
        quante += 1
    flash("Copiata con %d attività. Le iscrizioni sono CHIUSE e le date sono "
          "da mettere: correggi nome e date, poi riapri." % quante, "fatto")
    return redirect(url_for("riservato.modifica_manifestazione",
                            numero=copia["id"]))


# ------------------------------------------------------ singole iscrizioni

@riservato.route("/iscrizione/<int:numero>/annulla", methods=["POST"])
@serve_entrata
def annulla_iscrizione(numero):
    iscrizione = g.con.execute("SELECT * FROM iscrizione WHERE id = ?",
                               (numero,)).fetchone()
    if iscrizione is None:
        abort(404)
    nuovo_stato = ("confermata" if iscrizione["stato"] == "annullata"
                   else "annullata")
    g.con.execute("UPDATE iscrizione SET stato = ? WHERE id = ?",
                  (nuovo_stato, numero))
    flash("Iscrizione di %s %s %s. I dati restano in archivio."
          % (iscrizione["nome"], iscrizione["cognome"],
             "rimessa fra le valide" if nuovo_stato == "confermata"
             else "annullata"), "fatto")
    return redirect(url_for("riservato.manifestazione",
                            numero=iscrizione["manifestazione_id"]))


@riservato.route("/iscrizione/<int:numero>/cancella", methods=["GET", "POST"])
@serve_entrata
def cancella_iscrizione(numero):
    """Cancella per sempre una singola iscrizione gia' annullata."""
    iscrizione = g.con.execute("SELECT * FROM iscrizione WHERE id = ?",
                               (numero,)).fetchone()
    if iscrizione is None:
        abort(404)
    m = archivio.manifestazione_per_id(g.con,
                                       iscrizione["manifestazione_id"])

    if iscrizione["stato"] != "annullata":
        flash("Si cancellano solo le iscrizioni annullate. Prima annullala, "
              "poi potrai cancellarla.", "errore")
        return redirect(url_for("riservato.manifestazione", numero=m["id"]))

    if request.method == "POST":
        riepilogo = archivio.cancella_iscrizione_definitivamente(g.con, numero)
        archivio.ricompatta(g.con)
        print("  cancellata definitivamente l'iscrizione %s (%d persone)"
              % (riepilogo["codice"], riepilogo["persone"]))
        flash("Cancellata definitivamente l'iscrizione %s. Non è più "
              "recuperabile." % riepilogo["codice"], "fatto")
        return redirect(url_for("riservato.manifestazione", numero=m["id"]))

    return render_template(
        "riservato/cancella.html", m=m, quante=1,
        iscrizioni=[iscrizione],
        azione=url_for("riservato.cancella_iscrizione", numero=numero))


@riservato.route("/manifestazione/<int:numero>/cancella-annullate",
                 methods=["GET", "POST"])
@serve_entrata
def cancella_annullate(numero):
    """Cancella per sempre tutte le iscrizioni annullate di una
    manifestazione: serve per fare pulizia dopo la manifestazione."""
    m = archivio.manifestazione_per_id(g.con, numero)
    if m is None:
        abort(404)
    annullate = archivio.iscrizioni_annullate(g.con, numero)

    if not annullate:
        flash("Non c'è nessuna iscrizione annullata da cancellare.", "errore")
        return redirect(url_for("riservato.manifestazione", numero=numero))

    if request.method == "POST":
        quante, persone = 0, 0
        for iscrizione in annullate:
            riepilogo = archivio.cancella_iscrizione_definitivamente(
                g.con, iscrizione["id"])
            if riepilogo:
                quante += 1
                persone += riepilogo["persone"]
        archivio.ricompatta(g.con)
        print("  cancellate definitivamente %d iscrizioni annullate "
              "(%d persone) di «%s»" % (quante, persone, m["nome"]))
        flash("Cancellate definitivamente %d iscrizioni annullate. Non sono "
              "più recuperabili." % quante, "fatto")
        return redirect(url_for("riservato.manifestazione", numero=numero))

    return render_template(
        "riservato/cancella.html", m=m, quante=len(annullate),
        iscrizioni=annullate,
        azione=url_for("riservato.cancella_annullate", numero=numero))


@riservato.route("/riga/<int:numero>/conferma", methods=["POST"])
@serve_entrata
def conferma_riga(numero):
    """Fa passare una riga dalla lista d'attesa agli iscritti, ma solo se
    il posto c'e' davvero."""
    riga = g.con.execute(
        "SELECT ia.*, a.nome AS nome_attivita, a.posti, "
        "       a.manifestazione_id, i.nome, i.cognome "
        "  FROM iscrizione_attivita ia "
        "  JOIN attivita a ON a.id = ia.attivita_id "
        "  JOIN iscrizione i ON i.id = ia.iscrizione_id "
        " WHERE ia.id = ?", (numero,)).fetchone()
    if riga is None:
        abort(404)

    con = g.con
    con.execute("BEGIN IMMEDIATE")
    try:
        occupati = archivio.persone_confermate_per_attivita(
            con, riga["manifestazione_id"]).get(riga["attivita_id"], 0)
        rimasti = (None if riga["posti"] is None
                   else riga["posti"] - occupati)
        if rimasti is not None and rimasti < riga["persone"]:
            con.execute("ROLLBACK")
            flash("Non si può: su «%s» restano %d posti e servono %d."
                  % (riga["nome_attivita"], max(0, rimasti), riga["persone"]),
                  "errore")
        else:
            con.execute("UPDATE iscrizione_attivita SET stato = 'confermata' "
                        "WHERE id = ?", (numero,))
            con.execute("COMMIT")
            flash("%s %s: posto confermato su «%s» (%d persone)."
                  % (riga["nome"], riga["cognome"], riga["nome_attivita"],
                     riga["persone"]), "fatto")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return redirect(url_for("riservato.manifestazione",
                            numero=riga["manifestazione_id"]))


@riservato.route("/riga/<int:numero>/in_attesa", methods=["POST"])
@serve_entrata
def rimetti_in_attesa(numero):
    riga = g.con.execute(
        "SELECT ia.*, a.nome AS nome_attivita, a.manifestazione_id "
        "  FROM iscrizione_attivita ia "
        "  JOIN attivita a ON a.id = ia.attivita_id WHERE ia.id = ?",
        (numero,)).fetchone()
    if riga is None:
        abort(404)
    g.con.execute("UPDATE iscrizione_attivita SET stato = 'attesa' "
                  "WHERE id = ?", (numero,))
    flash("Rimesso in lista d'attesa su «%s»." % riga["nome_attivita"],
          "fatto")
    return redirect(url_for("riservato.manifestazione",
                            numero=riga["manifestazione_id"]))


# ------------------------------------------------------------ esportazione

@riservato.route("/manifestazione/<int:numero>/elenco.csv")
@serve_entrata
def esporta(numero):
    m = archivio.manifestazione_per_id(g.con, numero)
    if m is None:
        abort(404)
    iscrizioni = archivio.prospetto_iscrizioni(g.con, numero,
                                               includi_annullate=True)

    foglio = io.StringIO()
    # Il punto e virgola e' quello che Excel italiano si aspetta.
    scrittore = csv.writer(foglio, delimiter=";", quoting=csv.QUOTE_MINIMAL,
                           lineterminator="\r\n")
    scrittore.writerow([
        "Codice", "Inviata il", "Stato", "Tipo", "Nome", "Cognome",
        "Gruppo", "Persone", "Telefono", "Email", "Attività confermate",
        "In lista d'attesa", "Quota attesa (euro)", "Note",
        "Nomi dei partecipanti"])
    for voce in iscrizioni:
        iscrizione = voce["iscrizione"]
        scrittore.writerow([
            iscrizione["codice_conferma"],
            iscrizione["creata_il"],
            iscrizione["stato"],
            "gruppo" if iscrizione["tipo"] == "gruppo" else "singolo",
            iscrizione["nome"], iscrizione["cognome"],
            iscrizione["gruppo_nome"], iscrizione["numero_persone"],
            iscrizione["telefono"], iscrizione["email"],
            " | ".join(voce["confermate"]),
            " | ".join(voce["in_attesa"]),
            "%d,%02d" % divmod(voce["quota_centesimi"], 100),
            iscrizione["note"].replace("\n", " "),
            iscrizione["nomi_partecipanti"].replace("\n", " | ")])

    # BOM davanti: senza, Excel su Windows sbaglia gli accenti.
    contenuto = "﻿" + foglio.getvalue()
    nome_file = "iscritti-%s-%s.csv" % (m["codice"], oggi_iso())
    return Response(
        contenuto.encode("utf-8"),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=%s" % nome_file})
