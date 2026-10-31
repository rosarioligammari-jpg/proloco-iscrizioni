# applicazione/__init__.py -- costruzione del programma web.

import secrets
from pathlib import Path

from flask import Flask, g

from configurazione import (CARTELLA_DATI, COLLEGAMENTO_SICURO,
                            DIETRO_UN_PROXY, DIMENSIONE_MASSIMA_INVIO,
                            ENTE, NOMI_FILE_LOGO, NOME_FILE_CHIAVE,
                            TITOLO_SCHEDA, NOME_PROGRAMMA)
from applicazione import archivio, formato


def file_logo():
    """Nome del file del logo da mostrare in testata, oppure None.

    Il logo si mette nella cartella applicazione/static/ e basta: se c'e'
    compare, se manca le pagine funzionano lo stesso con il solo testo.
    """
    cartella = Path(__file__).resolve().parent / "static"
    for nome in NOMI_FILE_LOGO:
        if (cartella / nome).exists():
            return nome
    return None


def chiave_segreta():
    """La chiave dei cookie di sessione: generata al primo avvio e
    conservata in un file, cosi' i collegamenti non cadono ad ogni riavvio."""
    CARTELLA_DATI.mkdir(parents=True, exist_ok=True)
    percorso = CARTELLA_DATI / NOME_FILE_CHIAVE
    if not percorso.exists():
        percorso.write_text(secrets.token_hex(32), encoding="utf-8")
    return percorso.read_text(encoding="utf-8").strip()


def crea_applicazione():
    app = Flask(__name__,
                template_folder="templates",
                static_folder="static",
                static_url_path="/statico")
    app.config["SECRET_KEY"] = chiave_segreta()
    app.config["TITOLO_SCHEDA"] = TITOLO_SCHEDA
    app.config["NOME_PROGRAMMA"] = NOME_PROGRAMMA
    app.config["JSON_AS_ASCII"] = False
    app.config["MAX_CONTENT_LENGTH"] = DIMENSIONE_MASSIMA_INVIO

    # Il cookie dell'area riservata: mai leggibile dal JavaScript, mai
    # mandato a un altro sito, e solo cifrato quando siamo su https.
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = COLLEGAMENTO_SICURO

    if DIETRO_UN_PROXY:
        # Dietro a un tunnel, l'indirizzo di chi si collega e il nome
        # del sito arrivano in intestazioni a parte: senza questo, il
        # programma crederebbe che tutti vengano dal computer stesso.
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1,
                                x_host=1, x_prefix=1)

    archivio.prepara()
    formato.registra_filtri(app)

    @app.before_request
    def apri_archivio():
        g.con = archivio.connessione()

    @app.teardown_request
    def chiudi_archivio(errore=None):
        con = g.pop("con", None)
        if con is not None:
            con.close()

    @app.context_processor
    def valori_sempre_disponibili():
        return {"titolo_scheda": TITOLO_SCHEDA,
                "nome_programma": NOME_PROGRAMMA,
                "ente": ENTE,
                "file_logo": file_logo()}

    from applicazione.pubblico import pubblico
    from applicazione.riservato import riservato
    app.register_blueprint(pubblico)
    app.register_blueprint(riservato)

    return app
