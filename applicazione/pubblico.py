# pubblico.py -- le pagine che vedono i partecipanti.
#
# Sono le pagine che finiscono nel link mandato nei gruppi: devono
# funzionare bene dal telefono e non devono mai dare errori tecnici in
# faccia a chi si iscrive.

import secrets
from datetime import datetime, timedelta

from flask import (Blueprint, abort, g, redirect, render_template, request,
                   url_for)

from configurazione import (INVII_AL_MINUTO, LUNGHEZZA_CODICE_CONFERMA,
                            MASSIMO_PERSONE_PER_GRUPPO)
from applicazione import archivio, avvisi, posta
from applicazione.formato import (data_ora_italiana, euro_secco,
                                  oggi_iso, persone as dicitura_persone)

pubblico = Blueprint("pubblico", __name__)

# Quando ha inviato, l'ultimo minuto, ogni collegamento. Si tiene in
# memoria e si azzera al riavvio: non e' una registrazione di chi naviga,
# e' solo un freno contro gli invii a raffica.
_INVII_RECENTI = {}


def _troppi_invii():
    """Vero se da questo collegamento stanno arrivando troppe iscrizioni."""
    adesso = datetime.now()
    da_quando = adesso - timedelta(minutes=1)
    chi = request.remote_addr or "sconosciuto"

    # Pulizia: via i collegamenti che non inviano piu' da un pezzo.
    if len(_INVII_RECENTI) > 500:
        for chiave in [k for k, v in _INVII_RECENTI.items()
                       if not v or v[-1] < da_quando]:
            _INVII_RECENTI.pop(chiave, None)

    recenti = [quando for quando in _INVII_RECENTI.get(chi, [])
               if quando > da_quando]
    recenti.append(adesso)
    _INVII_RECENTI[chi] = recenti
    return len(recenti) > INVII_AL_MINUTO


# ------------------------------------------------------------------ aiuti

def _iscrizioni_chiuse(manifestazione):
    """Restituisce il motivo della chiusura, oppure None se sono aperte."""
    if not manifestazione["iscrizioni_aperte"]:
        return "Le iscrizioni sono chiuse."
    chiusura = manifestazione["chiusura_iscrizioni"]
    if chiusura and str(chiusura)[:10] < oggi_iso():
        return "Le iscrizioni si sono chiuse il %s." % (
            "/".join(reversed(str(chiusura)[:10].split("-"))))
    return None


def _prospetto_attivita(con, manifestazione):
    """Elenco delle attivita' con i posti occupati, rimasti e in attesa.

    Ogni voce e' un dizionario pronto per il template: niente conti
    dentro la pagina.
    """
    attivita = archivio.attivita_di(con, manifestazione["id"])
    occupati = archivio.persone_confermate_per_attivita(con, manifestazione["id"])
    in_attesa = archivio.persone_in_attesa_per_attivita(con, manifestazione["id"])
    prospetto = []
    for riga in attivita:
        presi = occupati.get(riga["id"], 0)
        rimasti = archivio.posti_rimasti(riga, presi)
        prospetto.append({
            "riga": riga,
            "id": riga["id"],
            "nome": riga["nome"],
            "descrizione": riga["descrizione"],
            "giorno": riga["giorno"],
            "ora_inizio": riga["ora_inizio"],
            "posti": riga["posti"],
            "quota_centesimi": riga["quota_centesimi"],
            "occupati": presi,
            "rimasti": rimasti,
            "in_attesa": in_attesa.get(riga["id"], 0),
            "al_completo": rimasti is not None and rimasti <= 0,
        })
    return prospetto


def _serve_la_lista_attesa(manifestazione, attivita):
    """Vero se c'e' almeno un'attivita' gia' al completo."""
    if not manifestazione["lista_attesa"]:
        return False
    return any(voce["al_completo"] for voce in attivita)


def _valori_inviati():
    """Quello che l'utente ha scritto, ripulito dagli spazi, per poterlo
    rimettere nel modulo se qualcosa va corretto."""
    moduli = request.form
    return {
        "tipo": moduli.get("tipo", "singolo"),
        "nome": moduli.get("nome", "").strip(),
        "cognome": moduli.get("cognome", "").strip(),
        "telefono": moduli.get("telefono", "").strip(),
        "email": moduli.get("email", "").strip(),
        "gruppo_nome": moduli.get("gruppo_nome", "").strip(),
        "numero_persone": moduli.get("numero_persone", "").strip(),
        "nomi_partecipanti": moduli.get("nomi_partecipanti", "").strip(),
        "note": moduli.get("note", "").strip(),
        "consenso": bool(moduli.get("consenso")),
        "accetta_attesa": bool(moduli.get("accetta_attesa")),
        "attivita": moduli.getlist("attivita"),
        "gettone": moduli.get("gettone", "").strip(),
        # Campo nascosto: una persona non lo vede e lo lascia vuoto, i
        # programmi automatici lo riempiono. Si chiama «trappola».
        "trappola": moduli.get("sito_web", "").strip(),
    }


# ----------------------------------------------------------------- pagine

@pubblico.route("/salute")
def salute():
    """Controllo automatico, come negli altri programmi dello studio.

    Dice soltanto se il programma risponde e se l'archivio si apre: non
    mostra nessun dato e non richiede password. La usa il server per
    accorgersi da solo se qualcosa si e' rotto.
    """
    try:
        g.con.execute("SELECT 1").fetchone()
    except Exception:
        return {"stato": "guasto", "archivio": "non raggiungibile"}, 503
    return {"stato": "va bene"}, 200


@pubblico.route("/")
def apertura():
    elenco = archivio.manifestazioni(g.con)
    aperte = [m for m in elenco if _iscrizioni_chiuse(m) is None]
    if len(aperte) == 1 and len(elenco) == 1:
        return redirect(url_for("pubblico.manifestazione",
                                codice=aperte[0]["codice"]))
    return render_template("elenco.html", manifestazioni=elenco,
                           chiusa=_iscrizioni_chiuse)


@pubblico.route("/m/<codice>")
def manifestazione(codice):
    riga = archivio.manifestazione_per_codice(g.con, codice)
    if riga is None:
        abort(404)
    attivita = _prospetto_attivita(g.con, riga)
    return render_template(
        "manifestazione.html",
        m=riga,
        attivita=attivita,
        motivo_chiusura=_iscrizioni_chiuse(riga),
        valori={"tipo": "singolo", "numero_persone": "2", "attivita": []},
        errori=[],
        # La spunta della lista d'attesa si mostra solo quando serve:
        # chiedere «se fosse al completo» mentre c'e' posto per tutti e'
        # una domanda senza senso, che fa solo esitare chi compila.
        mostra_attesa=_serve_la_lista_attesa(riga, attivita),
        massimo_gruppo=MASSIMO_PERSONE_PER_GRUPPO,
        gettone=secrets.token_urlsafe(24))


@pubblico.route("/m/<codice>", methods=["POST"])
def invia(codice):
    riga = archivio.manifestazione_per_codice(g.con, codice)
    if riga is None:
        abort(404)

    valori = _valori_inviati()

    if valori["trappola"]:
        return _rimostra(riga, valori, [
            "Non è stato possibile registrare l'iscrizione. Se stai "
            "leggendo questo messaggio e non sei un programma automatico, "
            "lascia vuoto il campo «sito web» e riprova, oppure contatta "
            "gli organizzatori."])

    if _troppi_invii():
        return _rimostra(riga, valori, [
            "Sono arrivate troppe iscrizioni di fila da questo "
            "collegamento. Aspetta un minuto e riprova: se stai iscrivendo "
            "tante persone, conviene usare «Iscrivo un gruppo»."])

    # Doppio clic sul pulsante: lo stesso gettone non produce due iscrizioni.
    gia_fatta = archivio.iscrizione_per_gettone(g.con, valori["gettone"])
    if gia_fatta is not None:
        return redirect(url_for("pubblico.iscritto", codice=codice,
                                codice_conferma=gia_fatta["codice_conferma"]))

    motivo_chiusura = _iscrizioni_chiuse(riga)
    if motivo_chiusura:
        return _rimostra(riga, valori, [motivo_chiusura])

    errori, numero_persone = _controlla(valori)
    if errori:
        return _rimostra(riga, valori, errori)

    # Dall'apertura della transazione al salvataggio nessun altro puo'
    # occupare gli stessi posti: i conti si rifanno qui dentro.
    con = g.con
    con.execute("BEGIN IMMEDIATE")
    try:
        occupati = archivio.persone_confermate_per_attivita(con, riga["id"])
        scelte, pieni = [], []
        for identificativo in valori["attivita"]:
            if not str(identificativo).isdigit():
                continue
            attivita = archivio.attivita_per_id(con, int(identificativo))
            if attivita is None or attivita["manifestazione_id"] != riga["id"] \
                    or not attivita["attiva"]:
                continue
            rimasti = archivio.posti_rimasti(
                attivita, occupati.get(attivita["id"], 0))
            if rimasti is None or rimasti >= numero_persone:
                scelte.append((attivita, "confermata"))
            elif riga["lista_attesa"] and valori["accetta_attesa"]:
                scelte.append((attivita, "attesa"))
            else:
                pieni.append((attivita, rimasti))

        # Se anche una sola attivita' scelta non ci sta, non si salva nulla:
        # meglio far correggere che iscrivere a meta' senza dirlo.
        if pieni:
            con.execute("ROLLBACK")
            return _rimostra(riga, valori,
                             [_messaggio_pieni(pieni, numero_persone, riga)],
                             offri_attesa=True)

        if not scelte:
            con.execute("ROLLBACK")
            return _rimostra(riga, valori, ["Scegli almeno un'attività."])

        codice_conferma = archivio.nuovo_codice_conferma(
            con, LUNGHEZZA_CODICE_CONFERMA)
        cursore = con.execute(
            "INSERT INTO iscrizione (manifestazione_id, codice_conferma, "
            "  gettone, tipo, nome, cognome, telefono, email, gruppo_nome, "
            "  numero_persone, nomi_partecipanti, note, consenso_privacy, "
            "  stato, creata_il) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'confermata', ?)",
            (riga["id"], codice_conferma, valori["gettone"] or None,
             valori["tipo"], valori["nome"], valori["cognome"],
             valori["telefono"], valori["email"], valori["gruppo_nome"],
             numero_persone, valori["nomi_partecipanti"], valori["note"],
             archivio.adesso()))
        iscrizione_id = cursore.lastrowid
        for attivita, stato in scelte:
            con.execute(
                "INSERT INTO iscrizione_attivita (iscrizione_id, attivita_id, "
                "  persone, stato) VALUES (?, ?, ?, ?)",
                (iscrizione_id, attivita["id"], numero_persone, stato))
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise

    # L'avviso agli organizzatori parte DOPO il salvataggio e in una
    # finestra a parte: se la posta non va, l'iscrizione resta comunque.
    # Anche preparare il messaggio e' protetto: nessun guaio qui dentro
    # deve mai arrivare in faccia a chi si e' appena iscritto.
    try:
        _avvisa_sul_telefono(riga, numero_persone, scelte)
        _avvisa_organizzatori(riga, valori, numero_persone, scelte,
                              codice_conferma)
    except Exception:
        import traceback
        print("  [avvisi] non sono riuscito a preparare l'avviso:")
        traceback.print_exc()

    return redirect(url_for("pubblico.iscritto", codice=codice,
                            codice_conferma=codice_conferma))


@pubblico.route("/m/<codice>/iscritto/<codice_conferma>")
def iscritto(codice, codice_conferma):
    riga = archivio.manifestazione_per_codice(g.con, codice)
    if riga is None:
        abort(404)
    iscrizione = archivio.iscrizione_per_codice(g.con, codice_conferma)
    if iscrizione is None or iscrizione["manifestazione_id"] != riga["id"]:
        abort(404)
    righe = archivio.righe_attivita_iscrizione(g.con, iscrizione["id"])
    totale = sum(r["quota_centesimi"] * r["persone"]
                 for r in righe if r["stato"] == "confermata")
    return render_template("inviata.html", m=riga, iscrizione=iscrizione,
                           righe=righe, totale_centesimi=totale)


# -------------------------------------------- avviso sul telefono (ntfy)

def _avvisa_sul_telefono(manifestazione, numero_persone, scelte):
    """Fa squillare il telefono degli organizzatori.

    NESSUN NOME esce da qui: si dice quante persone e su quali attività,
    mai chi. Chi vuole sapere il nome tocca il collegamento e lo trova
    nell'area riservata, dietro la password. Così l'informativa che
    firmano gli iscritti — «i dati non vengono comunicati a terzi» —
    resta vera.
    """
    canale = archivio.impostazione(g.con, avvisi.CHIAVE_CANALE, "")
    if not canale:
        return
    server = archivio.impostazione(g.con, avvisi.CHIAVE_SERVER,
                                   avvisi.SERVER_PREDEFINITO)

    totali = archivio.totali_manifestazione(g.con, manifestazione["id"])
    confermate = [a["nome"] for a, stato in scelte if stato == "confermata"]
    in_attesa = [a["nome"] for a, stato in scelte if stato == "attesa"]

    # Qualcosa si è appena riempito? È l'altra cosa che un organizzatore
    # vuole sapere subito.
    prospetto = {voce["id"]: voce for voce in
                 archivio.prospetto_attivita_riservato(
                     g.con, manifestazione["id"])}
    piene = [a["nome"] for a, stato in scelte
             if stato == "confermata"
             and prospetto.get(a["id"], {}).get("al_completo")]

    righe = []
    if confermate:
        righe.append("%s · %s" % (dicitura_persone(numero_persone),
                                  ", ".join(confermate)))
    if in_attesa:
        righe.append("In lista d'attesa: %s" % ", ".join(in_attesa))
    righe.append("Siamo in %d, su %d iscrizioni."
                 % (totali["persone"], totali["iscrizioni"]))
    if piene:
        righe.append("Adesso è al completo: %s" % ", ".join(piene))

    avvisi.manda_senza_far_danni(
        server, canale,
        "%s · nuova iscrizione" % manifestazione["nome"],
        "\n".join(righe),
        collegamento=url_for("riservato.manifestazione",
                             numero=manifestazione["id"], _external=True),
        etichette=["warning"] if piene else ["bell"])


# ------------------------------------------------- avviso agli organizzatori

def _avvisa_organizzatori(manifestazione, valori, numero_persone, scelte,
                          codice_conferma):
    """Manda un'email agli organizzatori per ogni iscrizione nuova.

    Nessun indirizzo scritto nella manifestazione = nessun avviso, e va
    benissimo: e' una scelta, non un guasto.
    """
    destinatari = posta.indirizzi(manifestazione["avvisi_a"]
                                  if "avvisi_a" in manifestazione.keys()
                                  else "")
    if not destinatari:
        return

    totali = archivio.totali_manifestazione(g.con, manifestazione["id"])

    righe = []
    quota = 0
    for attivita, stato in scelte:
        pezzo = "  - %s" % attivita["nome"]
        if stato == "attesa":
            pezzo += "   [IN LISTA D'ATTESA]"
        pezzo += " (%s" % dicitura_persone(numero_persone)
        if attivita["quota_centesimi"] and stato == "confermata":
            totale_voce = attivita["quota_centesimi"] * numero_persone
            quota += totale_voce
            pezzo += ", %s" % euro_secco(totale_voce)
        pezzo += ")"
        righe.append(pezzo)

    testo = ["Nuova iscrizione a «%s»." % manifestazione["nome"], ""]
    testo.append("Chi:       %s %s" % (valori["nome"], valori["cognome"]))
    if valori["gruppo_nome"]:
        if valori["tipo"] == "gruppo":
            testo.append("Gruppo:    %s (iscrive %s)"
                         % (valori["gruppo_nome"],
                            dicitura_persone(numero_persone)))
        else:
            testo.append("Gruppo:    %s" % valori["gruppo_nome"])
    testo.append("Telefono:  %s" % valori["telefono"])
    if valori["email"]:
        testo.append("Email:     %s" % valori["email"])
    testo.append("")
    testo.append("Attività:")
    testo.extend(righe)
    if valori["nomi_partecipanti"]:
        testo.append("")
        testo.append("Partecipanti:")
        for nome in valori["nomi_partecipanti"].splitlines():
            if nome.strip():
                testo.append("  - %s" % nome.strip())
    if valori["note"]:
        testo.append("")
        testo.append("Note: %s" % valori["note"])
    if quota:
        testo.append("")
        testo.append("Quota attesa: %s (si paga in loco)" % euro_secco(quota))
    testo.append("")
    testo.append("Codice dell'iscrizione: %s" % codice_conferma)
    testo.append("Inviata il %s" % data_ora_italiana(archivio.adesso()))
    testo.append("")
    testo.append("A oggi: %d persone su %d iscrizioni."
                 % (totali["persone"], totali["iscrizioni"]))
    if totali["persone_solo_attesa"]:
        testo.append("In lista d'attesa: %d persone."
                     % totali["persone_solo_attesa"])
    testo.append("")
    testo.append("Elenco completo e totali:")
    testo.append(url_for("riservato.manifestazione",
                         numero=manifestazione["id"], _external=True))
    testo.append("")
    testo.append("--")
    testo.append("Messaggio automatico del programma Iscrizioni.")
    testo.append("Non rispondere a questo messaggio: per parlare con chi si")
    testo.append("è iscritto usa il telefono scritto qui sopra.")

    oggetto = "Nuova iscrizione · %s · %s %s (%s)" % (
        manifestazione["nome"], valori["nome"], valori["cognome"],
        dicitura_persone(numero_persone))

    posta.spedisci_senza_far_danni(destinatari, oggetto, "\n".join(testo))


# -------------------------------------------------------------- controlli

def _controlla(valori):
    """Controlla quello che e' stato scritto. Restituisce (errori, persone).

    I messaggi sono scritti per chi si iscrive, non per chi programma.
    """
    errori = []
    if not valori["nome"]:
        errori.append("Manca il nome.")
    if not valori["cognome"]:
        errori.append("Manca il cognome.")
    if not valori["telefono"]:
        errori.append("Manca il numero di telefono: serve per avvisarti "
                      "se qualcosa cambia.")
    if not valori["consenso"]:
        errori.append("Per iscriverti devi spuntare il consenso al "
                      "trattamento dei dati.")
    if not valori["attivita"]:
        errori.append("Scegli almeno un'attività.")

    numero_persone = 1
    if valori["tipo"] == "gruppo":
        if not valori["gruppo_nome"]:
            errori.append("Manca il nome del gruppo.")
        try:
            numero_persone = int(valori["numero_persone"] or 0)
        except ValueError:
            numero_persone = 0
        if numero_persone < 2:
            errori.append("Per un gruppo indica almeno 2 persone. "
                          "Se ti iscrivi da solo scegli «mi iscrivo io».")
        elif numero_persone > MASSIMO_PERSONE_PER_GRUPPO:
            errori.append("Da questo modulo si possono iscrivere fino a "
                          "%d persone per volta: per un gruppo più grande "
                          "manda due iscrizioni o contatta gli "
                          "organizzatori." % MASSIMO_PERSONE_PER_GRUPPO)
            numero_persone = MASSIMO_PERSONE_PER_GRUPPO
    return errori, max(1, numero_persone)


def _messaggio_pieni(pieni, numero_persone, manifestazione):
    """Spiega quale attività non ci sta e cosa si può fare."""
    nomi = ", ".join("«%s» (posti rimasti: %d)" % (a["nome"], r)
                     for a, r in pieni)
    testo = ("Non c'è più posto per %d persone su: %s."
             % (numero_persone, nomi))
    if manifestazione["lista_attesa"]:
        testo += (" Puoi toglierla dalla scelta, ridurre il numero di "
                  "persone, oppure spuntare «mettimi in lista d'attesa» "
                  "qui sotto e invii di nuovo.")
    else:
        testo += (" Togli quell'attività dalla scelta oppure riduci il "
                  "numero di persone.")
    return testo


def _rimostra(manifestazione, valori, errori, offri_attesa=False):
    """Rimostra il modulo con quello che l'utente aveva già scritto.

    offri_attesa: da accendere quando il posto non basta per questo
    gruppo. Succede anche su attivita' che NON sono al completo (restano
    sei posti e il gruppo e' di dieci): in quel caso la spunta della lista
    d'attesa deve comparire, altrimenti il messaggio consiglia di spuntare
    una cosa che non c'e'.
    """
    attivita = _prospetto_attivita(g.con, manifestazione)
    return render_template(
        "manifestazione.html",
        m=manifestazione,
        attivita=attivita,
        motivo_chiusura=_iscrizioni_chiuse(manifestazione),
        valori=valori,
        errori=errori,
        mostra_attesa=(offri_attesa
                       or _serve_la_lista_attesa(manifestazione, attivita)),
        massimo_gruppo=MASSIMO_PERSONE_PER_GRUPPO,
        gettone=valori["gettone"] or secrets.token_urlsafe(24)), 400
