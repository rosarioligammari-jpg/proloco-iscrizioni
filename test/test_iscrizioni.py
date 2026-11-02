# test_iscrizioni.py -- prove automatiche del programma iscrizioni.
#
# Si lanciano dalla cartella del programma con:
#     python -m unittest discover -s test -v
#
# Le prove NON toccano il database vero: lavorano in una cartella
# temporanea che viene buttata alla fine.

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

import applicazione  # noqa: E402
from applicazione import archivio  # noqa: E402


class ProvaBase(unittest.TestCase):
    """Prepara un archivio vuoto e una manifestazione finta."""

    def setUp(self):
        self.cartella = Path(tempfile.mkdtemp(prefix="prova_iscrizioni_"))
        # Il freno contro gli invii a raffica tiene il conto in memoria:
        # si azzera a ogni prova, altrimenti una prova blocca la seguente.
        from applicazione import pubblico
        pubblico._INVII_RECENTI.clear()
        archivio.CARTELLA_DATI = self.cartella
        applicazione.CARTELLA_DATI = self.cartella
        archivio.prepara()

        self.app = applicazione.crea_applicazione()
        self.app.config["TESTING"] = True
        self.cliente = self.app.test_client()

        con = archivio.connessione()
        con.execute(
            "INSERT INTO manifestazione (codice, nome, informativa_privacy, "
            "  iscrizioni_aperte, lista_attesa, creata_il) "
            "VALUES ('festa', 'Festa di prova', 'Informativa.', 1, 1, ?)",
            (archivio.adesso(),))
        self.manifestazione_id = con.execute(
            "SELECT id FROM manifestazione WHERE codice='festa'").fetchone()["id"]
        # Una attivita' con 10 posti, una senza limite.
        con.execute(
            "INSERT INTO attivita (manifestazione_id, nome, posti, "
            "  quota_centesimi, ordine) VALUES (?, 'Pranzo', 10, 2000, 1)",
            (self.manifestazione_id,))
        con.execute(
            "INSERT INTO attivita (manifestazione_id, nome, posti, "
            "  quota_centesimi, ordine) VALUES (?, 'Passeggiata', NULL, 0, 2)",
            (self.manifestazione_id,))
        righe = con.execute(
            "SELECT id, nome FROM attivita WHERE manifestazione_id = ? "
            "ORDER BY ordine", (self.manifestazione_id,)).fetchall()
        self.pranzo = righe[0]["id"]
        self.passeggiata = righe[1]["id"]
        con.close()

    def tearDown(self):
        shutil.rmtree(self.cartella, ignore_errors=True)

    # ------------------------------------------------------------ aiuti

    def iscrivi(self, **cambiamenti):
        dati = {
            "tipo": "singolo",
            "nome": "Mario",
            "cognome": "Rossi",
            "telefono": "3330000000",
            "consenso": "1",
            "attivita": [str(self.pranzo)],
            "gettone": "gettone-%d" % len(cambiamenti),
        }
        dati.update(cambiamenti)
        return self.cliente.post("/m/festa", data=dati)

    def quante_iscrizioni(self):
        con = archivio.connessione()
        try:
            return con.execute(
                "SELECT COUNT(*) AS q FROM iscrizione").fetchone()["q"]
        finally:
            con.close()

    def persone_su(self, attivita_id, stato="confermata"):
        """Quante persone risultano su un'attivita'.

        Come nel programma, un'iscrizione ANNULLATA non conta: senza
        questo controllo la prova direbbe che il posto e' ancora occupato.
        """
        con = archivio.connessione()
        try:
            riga = con.execute(
                "SELECT COALESCE(SUM(ia.persone), 0) AS q "
                "  FROM iscrizione_attivita ia "
                "  JOIN iscrizione i ON i.id = ia.iscrizione_id "
                " WHERE ia.attivita_id = ? AND ia.stato = ? "
                "   AND i.stato = 'confermata'",
                (attivita_id, stato)).fetchone()
            return riga["q"]
        finally:
            con.close()


class ProvaIscrizioneSemplice(ProvaBase):

    def test_la_pagina_si_apre_e_mostra_i_posti(self):
        risposta = self.cliente.get("/m/festa")
        self.assertEqual(risposta.status_code, 200)
        pagina = risposta.get_data(as_text=True)
        self.assertIn("posti rimasti: 10 su 10", pagina)
        self.assertIn("posti non limitati", pagina)

    def test_una_persona_si_iscrive(self):
        risposta = self.iscrivi()
        self.assertEqual(risposta.status_code, 302)
        self.assertEqual(self.quante_iscrizioni(), 1)
        self.assertEqual(self.persone_su(self.pranzo), 1)

    def test_i_posti_rimasti_calano(self):
        self.iscrivi()
        pagina = self.cliente.get("/m/festa").get_data(as_text=True)
        self.assertIn("posti rimasti: 9 su 10", pagina)

    def test_la_pagina_di_conferma_mostra_il_codice(self):
        risposta = self.iscrivi()
        pagina = self.cliente.get(risposta.headers["Location"]).get_data(
            as_text=True)
        self.assertIn("Iscrizione registrata", pagina)
        self.assertIn("20,00 €", pagina)


class ProvaControlli(ProvaBase):

    def test_senza_consenso_non_si_iscrive(self):
        risposta = self.iscrivi(consenso="")
        self.assertEqual(risposta.status_code, 400)
        self.assertIn("consenso", risposta.get_data(as_text=True))
        self.assertEqual(self.quante_iscrizioni(), 0)

    def test_senza_attivita_non_si_iscrive(self):
        risposta = self.iscrivi(attivita=[])
        self.assertEqual(risposta.status_code, 400)
        self.assertEqual(self.quante_iscrizioni(), 0)

    def test_senza_telefono_non_si_iscrive(self):
        risposta = self.iscrivi(telefono="")
        self.assertEqual(risposta.status_code, 400)
        self.assertEqual(self.quante_iscrizioni(), 0)

    def test_quello_che_era_scritto_resta_nel_modulo(self):
        risposta = self.iscrivi(consenso="", nome="Giuseppina")
        self.assertIn("Giuseppina", risposta.get_data(as_text=True))

    def test_gruppo_senza_nome_del_gruppo_non_passa(self):
        risposta = self.iscrivi(tipo="gruppo", numero_persone="4",
                                gruppo_nome="")
        self.assertEqual(risposta.status_code, 400)
        self.assertEqual(self.quante_iscrizioni(), 0)

    def test_gruppo_di_una_persona_non_passa(self):
        risposta = self.iscrivi(tipo="gruppo", numero_persone="1",
                                gruppo_nome="Amici")
        self.assertEqual(risposta.status_code, 400)
        self.assertIn("almeno 2 persone", risposta.get_data(as_text=True))


class ProvaGruppiEPosti(ProvaBase):

    def test_un_gruppo_occupa_tutti_i_suoi_posti(self):
        self.iscrivi(tipo="gruppo", gruppo_nome="Moto Club",
                     numero_persone="4")
        self.assertEqual(self.persone_su(self.pranzo), 4)
        pagina = self.cliente.get("/m/festa").get_data(as_text=True)
        self.assertIn("posti rimasti: 6 su 10", pagina)

    def test_gruppo_troppo_grande_non_entra_e_non_salva_niente(self):
        risposta = self.iscrivi(tipo="gruppo", gruppo_nome="Comitiva",
                                numero_persone="12")
        self.assertEqual(risposta.status_code, 400)
        # Nella pagina l'apostrofo esce scritto &#39;, percio' si cerca
        # un pezzo di frase che non ne contiene.
        self.assertIn("posto per 12 persone", risposta.get_data(as_text=True))
        self.assertEqual(self.quante_iscrizioni(), 0)
        self.assertEqual(self.persone_su(self.pranzo), 0)

    def test_con_la_lista_di_attesa_il_gruppo_entra_in_attesa(self):
        risposta = self.iscrivi(tipo="gruppo", gruppo_nome="Comitiva",
                                numero_persone="12", accetta_attesa="1")
        self.assertEqual(risposta.status_code, 302)
        self.assertEqual(self.persone_su(self.pranzo), 0)
        self.assertEqual(self.persone_su(self.pranzo, "attesa"), 12)

    def test_attivita_piena_si_mostra_al_completo(self):
        self.iscrivi(tipo="gruppo", gruppo_nome="Tutti", numero_persone="10")
        pagina = self.cliente.get("/m/festa").get_data(as_text=True)
        self.assertIn("al completo", pagina)

    def test_se_una_sola_attivita_non_ci_sta_non_si_salva_nulla(self):
        # Il pranzo e' pieno, la passeggiata no: non deve entrare a meta'.
        self.iscrivi(tipo="gruppo", gruppo_nome="Tutti", numero_persone="10")
        risposta = self.iscrivi(
            attivita=[str(self.pranzo), str(self.passeggiata)],
            gettone="gettone-secondo")
        self.assertEqual(risposta.status_code, 400)
        self.assertEqual(self.persone_su(self.passeggiata), 0)


class ProvaDoppioClic(ProvaBase):

    def test_due_invii_con_lo_stesso_gettone_fanno_una_sola_iscrizione(self):
        dati = {"tipo": "singolo", "nome": "Mario", "cognome": "Rossi",
                "telefono": "333", "consenso": "1",
                "attivita": [str(self.pranzo)], "gettone": "sempre-uguale"}
        prima = self.cliente.post("/m/festa", data=dati)
        seconda = self.cliente.post("/m/festa", data=dati)
        self.assertEqual(prima.status_code, 302)
        self.assertEqual(seconda.status_code, 302)
        self.assertEqual(prima.headers["Location"],
                         seconda.headers["Location"])
        self.assertEqual(self.quante_iscrizioni(), 1)
        self.assertEqual(self.persone_su(self.pranzo), 1)


class ProvaChiusura(ProvaBase):

    def _chiudi(self):
        con = archivio.connessione()
        con.execute("UPDATE manifestazione SET iscrizioni_aperte = 0 "
                    "WHERE codice = 'festa'")
        con.close()

    def test_a_iscrizioni_chiuse_non_si_iscrive(self):
        self._chiudi()
        risposta = self.iscrivi()
        self.assertEqual(risposta.status_code, 400)
        self.assertEqual(self.quante_iscrizioni(), 0)

    def test_a_iscrizioni_chiuse_la_pagina_lo_dice(self):
        self._chiudi()
        pagina = self.cliente.get("/m/festa").get_data(as_text=True)
        self.assertIn("Le iscrizioni sono chiuse", pagina)

    def test_la_data_di_chiusura_passata_chiude_da_sola(self):
        con = archivio.connessione()
        con.execute("UPDATE manifestazione SET chiusura_iscrizioni = "
                    "'2020-01-01' WHERE codice = 'festa'")
        con.close()
        pagina = self.cliente.get("/m/festa").get_data(as_text=True)
        self.assertIn("Le iscrizioni si sono chiuse il 01/01/2020", pagina)


class ProvaAccenti(ProvaBase):
    """Nei testi che legge l'utente non ci devono essere accenti scritti
    con l'apostrofo: «attivita'» al posto di «attività».

    Il controllo si fa sulle pagine GIA' COSTRUITE e senza il codice
    JavaScript: cercare l'apostrofo dentro il codice darebbe falsi
    allarmi su cose come 'change' o 'numero_persone'.
    """

    PAROLE = ("attivita", "puo", "piu", "perche", "citta", "qualita",
              "sara", "gia", "cosi", "sanita", "unita", "meta")

    def _testo_visibile(self, indirizzo):
        import html
        import re
        pagina = self.cliente.get(indirizzo).get_data(as_text=True)
        pagina = re.sub(r"(?is)<(script|style).*?</\1>", " ", pagina)
        pagina = re.sub(r"(?s)<[^>]+>", " ", pagina)
        return html.unescape(pagina)

    def _controlla(self, indirizzo):
        import re
        testo = self._testo_visibile(indirizzo).lower()
        trovate = set()
        for parola in self.PAROLE:
            if re.search(r"\b%s'" % parola, testo):
                trovate.add(parola + "'")
        self.assertEqual(
            sorted(trovate), [],
            "In %s compaiono accenti scritti con l'apostrofo: %s"
            % (indirizzo, ", ".join(sorted(trovate))))

    def test_la_pagina_di_iscrizione_ha_gli_accenti_veri(self):
        self._controlla("/m/festa")

    def test_la_pagina_di_conferma_ha_gli_accenti_veri(self):
        risposta = self.iscrivi()
        self._controlla(risposta.headers["Location"])

    def test_la_pagina_delle_manifestazioni_ha_gli_accenti_veri(self):
        self._controlla("/")


class ProvaDifese(ProvaBase):
    """Le difese che servono quando il programma sta su internet."""

    def test_il_campo_trappola_riempito_non_salva_niente(self):
        risposta = self.iscrivi(sito_web="https://spazzatura.example")
        self.assertEqual(risposta.status_code, 400)
        self.assertEqual(self.quante_iscrizioni(), 0)

    def test_il_campo_trappola_c_e_nel_modulo(self):
        pagina = self.cliente.get("/m/festa").get_data(as_text=True)
        self.assertIn('name="sito_web"', pagina)
        self.assertIn('class="trappola"', pagina)

    def test_troppi_invii_di_fila_vengono_fermati(self):
        from configurazione import INVII_AL_MINUTO
        ultima = None
        for numero in range(INVII_AL_MINUTO + 2):
            ultima = self.iscrivi(gettone="gettone-raffica-%d" % numero,
                                  attivita=[str(self.passeggiata)])
        self.assertEqual(ultima.status_code, 400)
        self.assertIn("troppe iscrizioni", ultima.get_data(as_text=True))

    def test_sotto_il_limite_passano_tutte(self):
        from configurazione import INVII_AL_MINUTO
        for numero in range(INVII_AL_MINUTO):
            risposta = self.iscrivi(gettone="gettone-buono-%d" % numero,
                                    attivita=[str(self.passeggiata)])
            self.assertEqual(risposta.status_code, 302)
        self.assertEqual(self.quante_iscrizioni(), INVII_AL_MINUTO)


class ProvaImpostazioniDiPubblicazione(ProvaBase):
    """Le tre righe che si cambiano sul server Linux devono avere effetto."""

    def test_in_locale_il_cookie_non_pretende_https(self):
        self.assertFalse(self.app.config["SESSION_COOKIE_SECURE"])
        self.assertTrue(self.app.config["SESSION_COOKIE_HTTPONLY"])

    def test_acceso_il_collegamento_sicuro_il_cookie_viaggia_solo_cifrato(self):
        applicazione.COLLEGAMENTO_SICURO = True
        try:
            app = applicazione.crea_applicazione()
            self.assertTrue(app.config["SESSION_COOKIE_SECURE"])
        finally:
            applicazione.COLLEGAMENTO_SICURO = False

    def test_dietro_un_proxy_il_programma_legge_l_indirizzo_vero(self):
        applicazione.DIETRO_UN_PROXY = True
        try:
            app = applicazione.crea_applicazione()
            from werkzeug.middleware.proxy_fix import ProxyFix
            self.assertIsInstance(app.wsgi_app, ProxyFix)
        finally:
            applicazione.DIETRO_UN_PROXY = False

    def test_un_invio_enorme_viene_rifiutato(self):
        from configurazione import DIMENSIONE_MASSIMA_INVIO
        risposta = self.iscrivi(note="x" * (DIMENSIONE_MASSIMA_INVIO + 10))
        self.assertEqual(risposta.status_code, 413)
        self.assertEqual(self.quante_iscrizioni(), 0)


class ProvaSalute(ProvaBase):
    """La pagina che il server usa per accorgersi se il programma e' vivo."""

    def test_risponde_che_va_bene(self):
        risposta = self.cliente.get("/salute")
        self.assertEqual(risposta.status_code, 200)
        self.assertEqual(risposta.get_json()["stato"], "va bene")

    def test_non_chiede_la_password(self):
        # Deve rispondere anche senza essere entrati nell'area riservata.
        self.assertEqual(self.cliente.get("/salute").status_code, 200)

    def test_non_mostra_dati_delle_persone(self):
        self.iscrivi()
        testo = self.cliente.get("/salute").get_data(as_text=True)
        self.assertNotIn("Mario", testo)
        self.assertNotIn("3330000000", testo)


class ProvaImpostazioniDaFuori(unittest.TestCase):
    """Le impostazioni si devono poter cambiare da fuori, come fanno gli
    altri programmi dello studio dentro il contenitore."""

    def setUp(self):
        import configurazione
        self.configurazione = configurazione

    def _con_ambiente(self, nome, valore, funzione, *resto):
        import os
        prima = os.environ.get(nome)
        os.environ[nome] = valore
        try:
            return funzione(nome, *resto)
        finally:
            if prima is None:
                os.environ.pop(nome, None)
            else:
                os.environ[nome] = prima

    def test_un_numero_arriva_da_fuori(self):
        self.assertEqual(
            self._con_ambiente("PROVA_NUMERO", "8113",
                               self.configurazione._numero, 5021), 8113)

    def test_un_numero_sbagliato_non_rompe_niente(self):
        self.assertEqual(
            self._con_ambiente("PROVA_NUMERO", "ottomila",
                               self.configurazione._numero, 5021), 5021)

    def test_un_interruttore_si_accende_da_fuori(self):
        for scritto in ("1", "si", "true", "on"):
            self.assertTrue(
                self._con_ambiente("PROVA_SI", scritto,
                                   self.configurazione._acceso, False), scritto)
        for scritto in ("0", "no", "false", ""):
            self.assertFalse(
                self._con_ambiente("PROVA_NO", scritto,
                                   self.configurazione._acceso, False), scritto)

    def test_senza_variabile_resta_il_valore_di_sempre(self):
        self.assertEqual(
            self.configurazione._testo("NON_ESISTE_PROPRIO", "predefinito"),
            "predefinito")


class ProvaSpuntaListaAttesa(ProvaBase):
    """La spunta della lista d'attesa si mostra SOLO quando serve.

    Chiedere «se fosse al completo» mentre c'e' posto per tutti e' una
    domanda senza senso, che fa esitare chi compila.
    """

    SPUNTA = 'name="accetta_attesa"'

    def test_con_posto_per_tutti_la_spunta_non_compare(self):
        pagina = self.cliente.get("/m/festa").get_data(as_text=True)
        self.assertNotIn(self.SPUNTA, pagina)

    def test_quando_un_attivita_e_al_completo_la_spunta_compare(self):
        self.iscrivi(tipo="gruppo", gruppo_nome="Tutti", numero_persone="10")
        pagina = self.cliente.get("/m/festa").get_data(as_text=True)
        self.assertIn("al completo", pagina)
        self.assertIn(self.SPUNTA, pagina)

    def test_se_restano_posti_ma_non_bastano_la_spunta_compare(self):
        # Sei posti rimasti e un gruppo di dieci: l'attivita' NON e' al
        # completo, ma il posto non basta. Il messaggio consiglia la lista
        # d'attesa, quindi la spunta deve esserci davvero.
        self.iscrivi(tipo="gruppo", gruppo_nome="Primi", numero_persone="4")
        risposta = self.iscrivi(tipo="gruppo", gruppo_nome="Secondi",
                                numero_persone="10",
                                gettone="gettone-secondo-gruppo")
        self.assertEqual(risposta.status_code, 400)
        pagina = risposta.get_data(as_text=True)
        self.assertIn("posto per 10 persone", pagina)
        self.assertIn(self.SPUNTA, pagina)

    def test_se_la_manifestazione_non_prevede_l_attesa_non_compare_mai(self):
        con = archivio.connessione()
        con.execute("UPDATE manifestazione SET lista_attesa = 0 "
                    "WHERE codice = 'festa'")
        con.close()
        self.iscrivi(tipo="gruppo", gruppo_nome="Tutti", numero_persone="10")
        pagina = self.cliente.get("/m/festa").get_data(as_text=True)
        self.assertIn("al completo", pagina)
        self.assertNotIn(self.SPUNTA, pagina)


if __name__ == "__main__":
    unittest.main()
