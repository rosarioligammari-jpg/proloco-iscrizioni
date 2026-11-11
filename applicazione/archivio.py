# archivio.py -- il database SQLite del programma iscrizioni.
#
# Regole di questo file:
#   - i percorsi arrivano da configurazione.py (pathlib), mai scritti a mano;
#   - le date si scrivono in archivio in formato ISO (aaaa-mm-gg) e si
#     mostrano a schermo in formato italiano (gg/mm/aaaa): la conversione
#     sta in formato.py, non qui;
#   - gli importi si tengono in centesimi interi, mai in virgola mobile.

import hashlib
import secrets
import sqlite3
from datetime import datetime

from configurazione import CARTELLA_DATI, NOME_DATABASE

SCHEMA = """
CREATE TABLE IF NOT EXISTS manifestazione (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    codice                  TEXT    NOT NULL UNIQUE,
    nome                    TEXT    NOT NULL,
    sottotitolo             TEXT    NOT NULL DEFAULT '',
    descrizione             TEXT    NOT NULL DEFAULT '',
    luogo                   TEXT    NOT NULL DEFAULT '',
    data_inizio             TEXT,
    data_fine               TEXT,
    organizzatore           TEXT    NOT NULL DEFAULT '',
    contatto_organizzatore  TEXT    NOT NULL DEFAULT '',
    informativa_privacy     TEXT    NOT NULL DEFAULT '',
    iscrizioni_aperte       INTEGER NOT NULL DEFAULT 1,
    chiusura_iscrizioni     TEXT,
    lista_attesa            INTEGER NOT NULL DEFAULT 1,
    avvisi_a                TEXT    NOT NULL DEFAULT '',
    creata_il               TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS attivita (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    manifestazione_id  INTEGER NOT NULL REFERENCES manifestazione(id),
    nome               TEXT    NOT NULL,
    descrizione        TEXT    NOT NULL DEFAULT '',
    giorno             TEXT,
    ora_inizio         TEXT    NOT NULL DEFAULT '',
    posti              INTEGER,
    quota_centesimi    INTEGER NOT NULL DEFAULT 0,
    ordine             INTEGER NOT NULL DEFAULT 0,
    attiva             INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS iscrizione (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    manifestazione_id  INTEGER NOT NULL REFERENCES manifestazione(id),
    codice_conferma    TEXT    NOT NULL UNIQUE,
    gettone            TEXT    UNIQUE,
    tipo               TEXT    NOT NULL DEFAULT 'singolo',
    nome               TEXT    NOT NULL,
    cognome            TEXT    NOT NULL,
    telefono           TEXT    NOT NULL DEFAULT '',
    email              TEXT    NOT NULL DEFAULT '',
    gruppo_nome        TEXT    NOT NULL DEFAULT '',
    numero_persone     INTEGER NOT NULL DEFAULT 1,
    nomi_partecipanti  TEXT    NOT NULL DEFAULT '',
    note               TEXT    NOT NULL DEFAULT '',
    consenso_privacy   INTEGER NOT NULL DEFAULT 0,
    stato              TEXT    NOT NULL DEFAULT 'confermata',
    creata_il          TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS iscrizione_attivita (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    iscrizione_id  INTEGER NOT NULL REFERENCES iscrizione(id),
    attivita_id    INTEGER NOT NULL REFERENCES attivita(id),
    persone        INTEGER NOT NULL DEFAULT 1,
    stato          TEXT    NOT NULL DEFAULT 'confermata',
    UNIQUE (iscrizione_id, attivita_id)
);

CREATE TABLE IF NOT EXISTS impostazione (
    chiave  TEXT PRIMARY KEY,
    valore  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attivita_manifestazione
    ON attivita (manifestazione_id, ordine);
CREATE INDEX IF NOT EXISTS idx_iscrizione_manifestazione
    ON iscrizione (manifestazione_id, stato);
CREATE INDEX IF NOT EXISTS idx_iscrizione_attivita_attivita
    ON iscrizione_attivita (attivita_id, stato);
"""


# ------------------------------------------------------------- connessione

def percorso_database():
    """Percorso del file del database, creando la cartella se manca."""
    CARTELLA_DATI.mkdir(parents=True, exist_ok=True)
    return CARTELLA_DATI / NOME_DATABASE


def connessione():
    """Apre una connessione al database.

    isolation_level=None: le transazioni le governiamo noi, con
    BEGIN IMMEDIATE dove serve contare i posti senza sorprese.
    """
    con = sqlite3.connect(str(percorso_database()), isolation_level=None,
                          timeout=15.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


# Colonne aggiunte dopo che il programma era gia' in uso. Si aggiungono
# da sole al primo avvio: nessun dato viene toccato, e un archivio gia'
# aggiornato non se ne accorge nemmeno.
COLONNE_AGGIUNTE = (
    ("manifestazione", "avvisi_a", "TEXT NOT NULL DEFAULT ''"),
)


def _aggiungi_colonne_mancanti(con):
    for tabella, colonna, tipo in COLONNE_AGGIUNTE:
        esistenti = [riga["name"] for riga in
                     con.execute("PRAGMA table_info(%s)" % tabella).fetchall()]
        if colonna not in esistenti:
            con.execute("ALTER TABLE %s ADD COLUMN %s %s"
                        % (tabella, colonna, tipo))
            print("  archivio: aggiunta la colonna %s.%s" % (tabella, colonna))


def prepara():
    """Crea le tabelle se non esistono. Si chiama ad ogni avvio."""
    con = connessione()
    try:
        con.executescript(SCHEMA)
        _aggiungi_colonne_mancanti(con)
    finally:
        con.close()


def adesso():
    """Data e ora correnti in formato ISO, come si scrivono in archivio."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ------------------------------------------------------------- impostazioni

def impostazione(con, chiave, predefinito=None):
    riga = con.execute("SELECT valore FROM impostazione WHERE chiave = ?",
                       (chiave,)).fetchone()
    return riga["valore"] if riga else predefinito


def scrivi_impostazione(con, chiave, valore):
    con.execute(
        "INSERT INTO impostazione (chiave, valore) VALUES (?, ?) "
        "ON CONFLICT(chiave) DO UPDATE SET valore = excluded.valore",
        (chiave, str(valore)))


# -------------------------------------------------- password area riservata

def cifra_password(password, sale=None):
    """Impronta della password: in archivio non finisce mai il testo in chiaro."""
    sale = sale or secrets.token_hex(16)
    impronta = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                   sale.encode("utf-8"), 200000).hex()
    return "%s$%s" % (sale, impronta)


def password_corretta(password, conservata):
    if not conservata or "$" not in conservata:
        return False
    sale, _ = conservata.split("$", 1)
    return secrets.compare_digest(cifra_password(password, sale), conservata)


# ------------------------------------------------------------ manifestazioni

def manifestazione_per_codice(con, codice):
    return con.execute("SELECT * FROM manifestazione WHERE codice = ?",
                       (codice,)).fetchone()


def manifestazione_per_id(con, manifestazione_id):
    return con.execute("SELECT * FROM manifestazione WHERE id = ?",
                       (manifestazione_id,)).fetchone()


def manifestazioni(con):
    return con.execute(
        "SELECT * FROM manifestazione ORDER BY "
        "COALESCE(data_inizio, '9999-12-31') DESC, id DESC").fetchall()


def attivita_di(con, manifestazione_id, solo_attive=True):
    sql = ("SELECT * FROM attivita WHERE manifestazione_id = ?"
           + (" AND attiva = 1" if solo_attive else "")
           + " ORDER BY ordine, COALESCE(giorno, '9999-12-31'), ora_inizio, id")
    return con.execute(sql, (manifestazione_id,)).fetchall()


def attivita_per_id(con, attivita_id):
    return con.execute("SELECT * FROM attivita WHERE id = ?",
                       (attivita_id,)).fetchone()


# ------------------------------------------------------------ conteggi posti

def _conteggio(con, manifestazione_id, stato):
    righe = con.execute(
        "SELECT ia.attivita_id AS id, SUM(ia.persone) AS persone "
        "  FROM iscrizione_attivita ia "
        "  JOIN iscrizione i ON i.id = ia.iscrizione_id "
        "  JOIN attivita a   ON a.id = ia.attivita_id "
        " WHERE a.manifestazione_id = ? "
        "   AND ia.stato = ? AND i.stato = 'confermata' "
        " GROUP BY ia.attivita_id", (manifestazione_id, stato)).fetchall()
    return {riga["id"]: (riga["persone"] or 0) for riga in righe}


def persone_confermate_per_attivita(con, manifestazione_id):
    """Quante persone risultano confermate su ogni attivita'.

    Restituisce un dizionario {attivita_id: persone}.
    """
    return _conteggio(con, manifestazione_id, "confermata")


def persone_in_attesa_per_attivita(con, manifestazione_id):
    """Quante persone risultano in lista d'attesa su ogni attivita'."""
    return _conteggio(con, manifestazione_id, "attesa")


def posti_rimasti(attivita_riga, occupati):
    """Posti ancora liberi, oppure None se l'attivita' e' senza limite."""
    if attivita_riga["posti"] is None:
        return None
    return max(0, attivita_riga["posti"] - occupati)


# -------------------------------------------------------------- iscrizioni

def iscrizione_per_gettone(con, gettone):
    """Serve contro il doppio clic: lo stesso gettone non entra due volte."""
    if not gettone:
        return None
    return con.execute("SELECT * FROM iscrizione WHERE gettone = ?",
                       (gettone,)).fetchone()


def iscrizione_per_codice(con, codice_conferma):
    return con.execute("SELECT * FROM iscrizione WHERE codice_conferma = ?",
                       (codice_conferma,)).fetchone()


def iscrizioni_di(con, manifestazione_id, includi_annullate=False):
    sql = ("SELECT * FROM iscrizione WHERE manifestazione_id = ?"
           + ("" if includi_annullate else " AND stato = 'confermata'")
           + " ORDER BY id")
    return con.execute(sql, (manifestazione_id,)).fetchall()


def righe_attivita_iscrizione(con, iscrizione_id):
    return con.execute(
        "SELECT ia.*, a.nome, a.giorno, a.ora_inizio, a.quota_centesimi "
        "  FROM iscrizione_attivita ia "
        "  JOIN attivita a ON a.id = ia.attivita_id "
        " WHERE ia.iscrizione_id = ? "
        " ORDER BY a.ordine, a.id", (iscrizione_id,)).fetchall()


# ------------------------------------------- prospetti per l'organizzatore

def prospetto_attivita_riservato(con, manifestazione_id):
    """Per ogni attivita': posti, confermati, rimasti, in attesa e quanto
    si incassera' se tutti pagano."""
    confermati = persone_confermate_per_attivita(con, manifestazione_id)
    in_attesa = persone_in_attesa_per_attivita(con, manifestazione_id)
    prospetto = []
    for riga in attivita_di(con, manifestazione_id, solo_attive=False):
        presi = confermati.get(riga["id"], 0)
        prospetto.append({
            "riga": riga,
            "id": riga["id"],
            "confermati": presi,
            "rimasti": posti_rimasti(riga, presi),
            "in_attesa": in_attesa.get(riga["id"], 0),
            "al_completo": (riga["posti"] is not None
                            and presi >= riga["posti"]),
            "incasso_centesimi": presi * riga["quota_centesimi"],
        })
    return prospetto


def prospetto_iscrizioni(con, manifestazione_id, includi_annullate=False):
    """Elenco degli iscritti gia' pronto per la pagina e per il CSV."""
    prospetto = []
    for iscrizione in iscrizioni_di(con, manifestazione_id,
                                    includi_annullate=includi_annullate):
        righe = righe_attivita_iscrizione(con, iscrizione["id"])
        confermate = [r["nome"] for r in righe if r["stato"] == "confermata"]
        in_attesa = [r["nome"] for r in righe if r["stato"] == "attesa"]
        quota = sum(r["quota_centesimi"] * r["persone"]
                    for r in righe if r["stato"] == "confermata")
        prospetto.append({
            "iscrizione": iscrizione,
            "righe": righe,
            "confermate": confermate,
            "in_attesa": in_attesa,
            "quota_centesimi": quota,
        })
    return prospetto


def totali_manifestazione(con, manifestazione_id):
    """I numeri che servono a colpo d'occhio.

    «persone» e' la risposta alla domanda «quanti saremo»: conta una volta
    sola chi si e' iscritto a piu' attivita', e non conta chi e' soltanto
    in lista d'attesa.
    """
    riga = con.execute(
        "SELECT COUNT(*) AS iscrizioni, "
        "       COALESCE(SUM(numero_persone), 0) AS persone "
        "  FROM iscrizione i "
        " WHERE i.manifestazione_id = ? AND i.stato = 'confermata' "
        "   AND EXISTS (SELECT 1 FROM iscrizione_attivita ia "
        "                WHERE ia.iscrizione_id = i.id "
        "                  AND ia.stato = 'confermata')",
        (manifestazione_id,)).fetchone()

    solo_attesa = con.execute(
        "SELECT COUNT(*) AS iscrizioni, "
        "       COALESCE(SUM(numero_persone), 0) AS persone "
        "  FROM iscrizione i "
        " WHERE i.manifestazione_id = ? AND i.stato = 'confermata' "
        "   AND NOT EXISTS (SELECT 1 FROM iscrizione_attivita ia "
        "                    WHERE ia.iscrizione_id = i.id "
        "                      AND ia.stato = 'confermata')",
        (manifestazione_id,)).fetchone()

    annullate = con.execute(
        "SELECT COUNT(*) AS quante FROM iscrizione "
        " WHERE manifestazione_id = ? AND stato = 'annullata'",
        (manifestazione_id,)).fetchone()["quante"]

    incasso = con.execute(
        "SELECT COALESCE(SUM(a.quota_centesimi * ia.persone), 0) AS totale "
        "  FROM iscrizione_attivita ia "
        "  JOIN attivita a   ON a.id = ia.attivita_id "
        "  JOIN iscrizione i ON i.id = ia.iscrizione_id "
        " WHERE a.manifestazione_id = ? AND ia.stato = 'confermata' "
        "   AND i.stato = 'confermata'",
        (manifestazione_id,)).fetchone()["totale"]

    return {
        "iscrizioni": riga["iscrizioni"],
        "persone": riga["persone"],
        "iscrizioni_solo_attesa": solo_attesa["iscrizioni"],
        "persone_solo_attesa": solo_attesa["persone"],
        "annullate": annullate,
        "incasso_centesimi": incasso,
    }


def nuovo_codice_conferma(con, lunghezza):
    """Codice breve, leggibile al telefono: niente O/0 ne' I/1."""
    alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(50):
        codice = "".join(secrets.choice(alfabeto) for _ in range(lunghezza))
        if iscrizione_per_codice(con, codice) is None:
            return codice
    raise RuntimeError("Non riesco a generare un codice di conferma libero.")
