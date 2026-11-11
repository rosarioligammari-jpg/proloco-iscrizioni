# test_area_riservata.py -- prove dell'area dell'organizzatore.
#
# Si lanciano insieme alle altre:
#     python -m unittest discover -s test -v

import unittest

from test_iscrizioni import ProvaBase
from applicazione import archivio


class ProvaAreaRiservata(ProvaBase):
    """Password, totali, attivita', iscritti, esportazione."""

    PASSWORD = "proloco2026"

    def setUp(self):
        super().setUp()
        from applicazione import riservato
        riservato._TENTATIVI["quanti"] = 0
        riservato._TENTATIVI["fino_a"] = None

    def crea_password(self):
        return self.cliente.post("/riservato/entrata",
                                 data={"password": self.PASSWORD,
                                       "ripetuta": self.PASSWORD})

    def entra(self):
        self.crea_password()
        self.cliente.post("/riservato/uscita")
        return self.cliente.post("/riservato/entrata",
                                 data={"password": self.PASSWORD})

    # ------------------------------------------------------------ porta

    def test_senza_password_non_si_entra(self):
        risposta = self.cliente.get("/riservato/")
        self.assertEqual(risposta.status_code, 302)
        self.assertIn("/riservato/entrata", risposta.headers["Location"])

    def test_la_prima_volta_chiede_di_creare_la_password(self):
        pagina = self.cliente.get("/riservato/entrata").get_data(as_text=True)
        self.assertIn("Prima volta", pagina)

    def test_la_password_troppo_corta_non_passa(self):
        self.cliente.post("/riservato/entrata",
                          data={"password": "corta", "ripetuta": "corta"})
        self.assertEqual(self.cliente.get("/riservato/").status_code, 302)

    def test_le_due_password_devono_coincidere(self):
        self.cliente.post("/riservato/entrata",
                          data={"password": "proloco2026",
                                "ripetuta": "proloco2027"})
        self.assertEqual(self.cliente.get("/riservato/").status_code, 302)

    def test_creata_la_password_si_entra(self):
        self.crea_password()
        self.assertEqual(self.cliente.get("/riservato/").status_code, 200)

    def test_la_password_sbagliata_non_fa_entrare(self):
        self.entra()
        self.cliente.post("/riservato/uscita")
        self.cliente.post("/riservato/entrata", data={"password": "altro"})
        self.assertEqual(self.cliente.get("/riservato/").status_code, 302)

    def test_la_password_non_si_conserva_in_chiaro(self):
        self.crea_password()
        con = archivio.connessione()
        try:
            conservata = archivio.impostazione(con, "password_area_riservata")
        finally:
            con.close()
        self.assertNotIn(self.PASSWORD, conservata)
        self.assertTrue(archivio.password_corretta(self.PASSWORD, conservata))

    # ----------------------------------------------------------- numeri

    def test_quanti_saremo_non_conta_due_volte_chi_fa_due_attivita(self):
        self.iscrivi(tipo="gruppo", gruppo_nome="Amici", numero_persone="4",
                     attivita=[str(self.pranzo), str(self.passeggiata)])
        con = archivio.connessione()
        try:
            totali = archivio.totali_manifestazione(con, self.manifestazione_id)
        finally:
            con.close()
        self.assertEqual(totali["persone"], 4)
        self.assertEqual(totali["iscrizioni"], 1)
        self.assertEqual(totali["incasso_centesimi"], 8000)   # 4 x 20,00

    def test_chi_e_solo_in_attesa_non_conta_fra_i_presenti(self):
        self.iscrivi(tipo="gruppo", gruppo_nome="Comitiva",
                     numero_persone="12", accetta_attesa="1")
        con = archivio.connessione()
        try:
            totali = archivio.totali_manifestazione(con, self.manifestazione_id)
        finally:
            con.close()
        self.assertEqual(totali["persone"], 0)
        self.assertEqual(totali["persone_solo_attesa"], 12)

    # --------------------------------------------------- manifestazioni

    def test_si_crea_una_manifestazione_da_schermo(self):
        self.entra()
        risposta = self.cliente.post("/riservato/manifestazione/nuova", data={
            "nome": "Sagra della salsiccia",
            "informativa_privacy": "I dati servono solo per la sagra.",
            "iscrizioni_aperte": "1"})
        self.assertEqual(risposta.status_code, 302)
        con = archivio.connessione()
        try:
            nuova = archivio.manifestazione_per_codice(
                con, "sagra-della-salsiccia")
        finally:
            con.close()
        self.assertIsNotNone(nuova)
        self.assertEqual(nuova["nome"], "Sagra della salsiccia")

    def test_senza_informativa_la_manifestazione_non_si_crea(self):
        self.entra()
        risposta = self.cliente.post("/riservato/manifestazione/nuova",
                                     data={"nome": "Senza informativa"})
        self.assertEqual(risposta.status_code, 400)
        self.assertIn("informativa", risposta.get_data(as_text=True))

    def test_due_manifestazioni_con_lo_stesso_nome_hanno_link_diversi(self):
        self.entra()
        for _ in range(2):
            self.cliente.post("/riservato/manifestazione/nuova", data={
                "nome": "Festa dei motori",
                "informativa_privacy": "Informativa."})
        con = archivio.connessione()
        try:
            self.assertIsNotNone(
                archivio.manifestazione_per_codice(con, "festa-dei-motori"))
            self.assertIsNotNone(
                archivio.manifestazione_per_codice(con, "festa-dei-motori-2"))
        finally:
            con.close()

    def test_la_chiusura_delle_iscrizioni_si_accende_e_si_spegne(self):
        self.entra()
        self.cliente.post("/riservato/manifestazione/%d/apertura"
                          % self.manifestazione_id)
        pagina = self.cliente.get("/m/festa").get_data(as_text=True)
        self.assertIn("Le iscrizioni sono chiuse", pagina)
        self.cliente.post("/riservato/manifestazione/%d/apertura"
                          % self.manifestazione_id)
        self.assertNotIn("Le iscrizioni sono chiuse",
                         self.cliente.get("/m/festa").get_data(as_text=True))

    def test_duplicare_copia_le_attivita_ma_non_gli_iscritti(self):
        self.iscrivi()
        self.entra()
        risposta = self.cliente.post("/riservato/manifestazione/%d/duplica"
                                     % self.manifestazione_id)
        self.assertEqual(risposta.status_code, 302)
        con = archivio.connessione()
        try:
            copia = archivio.manifestazione_per_codice(
                con, "festa-di-prova-copia")
            self.assertIsNotNone(copia)
            self.assertEqual(len(archivio.attivita_di(con, copia["id"])), 2)
            self.assertEqual(len(archivio.iscrizioni_di(con, copia["id"])), 0)
            self.assertEqual(copia["iscrizioni_aperte"], 0)
        finally:
            con.close()

    # -------------------------------------------------------- attivita'

    def test_si_aggiunge_un_attivita_con_posti_e_quota(self):
        self.entra()
        self.cliente.post("/riservato/manifestazione/%d/attivita/nuova"
                          % self.manifestazione_id,
                          data={"nome": "Cena", "posti": "80",
                                "quota": "25,50", "ora_inizio": "20:00"})
        con = archivio.connessione()
        try:
            righe = archivio.attivita_di(con, self.manifestazione_id)
            cena = [r for r in righe if r["nome"] == "Cena"][0]
        finally:
            con.close()
        self.assertEqual(cena["posti"], 80)
        self.assertEqual(cena["quota_centesimi"], 2550)

    def test_posti_vuoti_significa_senza_limite(self):
        self.entra()
        self.cliente.post("/riservato/manifestazione/%d/attivita/nuova"
                          % self.manifestazione_id,
                          data={"nome": "Corteo", "posti": "", "quota": ""})
        con = archivio.connessione()
        try:
            righe = archivio.attivita_di(con, self.manifestazione_id)
            corteo = [r for r in righe if r["nome"] == "Corteo"][0]
        finally:
            con.close()
        self.assertIsNone(corteo["posti"])
        self.assertEqual(corteo["quota_centesimi"], 0)

    def test_non_si_puo_scendere_sotto_i_posti_gia_occupati(self):
        self.iscrivi(tipo="gruppo", gruppo_nome="Amici", numero_persone="6")
        self.entra()
        risposta = self.cliente.post(
            "/riservato/attivita/%d/modifica" % self.pranzo,
            data={"nome": "Pranzo", "posti": "3", "quota": "20,00"})
        self.assertEqual(risposta.status_code, 400)
        self.assertIn("6 persone iscritte", risposta.get_data(as_text=True))

    def test_un_attivita_sospesa_sparisce_dal_modulo(self):
        self.entra()
        self.cliente.post("/riservato/attivita/%d/sospendi" % self.pranzo)
        pagina = self.cliente.get("/m/festa").get_data(as_text=True)
        # Il nome resta nel messaggio di conferma: si guarda la casella.
        self.assertNotIn('name="attivita" value="%d"' % self.pranzo, pagina)
        self.assertIn('name="attivita" value="%d"' % self.passeggiata, pagina)

    # ------------------------------------------------ singole iscrizioni

    def test_annullare_un_iscrizione_non_la_cancella(self):
        self.iscrivi()
        self.entra()
        con = archivio.connessione()
        numero = con.execute("SELECT id FROM iscrizione").fetchone()["id"]
        con.close()
        self.cliente.post("/riservato/iscrizione/%d/annulla" % numero)
        con = archivio.connessione()
        try:
            riga = con.execute("SELECT * FROM iscrizione WHERE id = ?",
                               (numero,)).fetchone()
            totali = archivio.totali_manifestazione(con, self.manifestazione_id)
        finally:
            con.close()
        self.assertIsNotNone(riga)
        self.assertEqual(riga["stato"], "annullata")
        self.assertEqual(totali["persone"], 0)
        self.assertEqual(totali["annullate"], 1)
        self.assertEqual(self.persone_su(self.pranzo), 0)

    def test_dalla_lista_di_attesa_si_da_il_posto_solo_se_c_e(self):
        self.iscrivi(tipo="gruppo", gruppo_nome="Comitiva",
                     numero_persone="12", accetta_attesa="1")
        self.entra()
        con = archivio.connessione()
        riga = con.execute("SELECT id FROM iscrizione_attivita "
                           "WHERE stato = 'attesa'").fetchone()
        con.close()
        # Dodici persone in dieci posti non ci stanno: deve rifiutare.
        self.cliente.post("/riservato/riga/%d/conferma" % riga["id"])
        self.assertEqual(self.persone_su(self.pranzo), 0)
        # Portati i posti a 20, il posto si puo' dare.
        self.cliente.post("/riservato/attivita/%d/modifica" % self.pranzo,
                          data={"nome": "Pranzo", "posti": "20",
                                "quota": "20,00"})
        self.cliente.post("/riservato/riga/%d/conferma" % riga["id"])
        self.assertEqual(self.persone_su(self.pranzo), 12)

    # ---------------------------------------------------- esportazione

    def test_l_elenco_si_scarica_per_excel(self):
        self.iscrivi(tipo="gruppo", gruppo_nome="Moto Club",
                     numero_persone="3")
        self.entra()
        risposta = self.cliente.get("/riservato/manifestazione/%d/elenco.csv"
                                    % self.manifestazione_id)
        self.assertEqual(risposta.status_code, 200)
        self.assertIn("attachment", risposta.headers["Content-Disposition"])
        testo = risposta.get_data().decode("utf-8")
        self.assertTrue(testo.startswith("﻿"))   # il segno per Excel
        self.assertIn("Moto Club", testo)
        self.assertIn("60,00", testo)                 # 3 x 20,00
        self.assertIn(";", testo)

    # ------------------------------------------- il modulo non deve bloccare

    def test_il_modulo_nuovo_arriva_con_l_informativa_gia_scritta(self):
        self.entra()
        pagina = self.cliente.get(
            "/riservato/manifestazione/nuova").get_data(as_text=True)
        self.assertIn("sono raccolti da Pro Loco Villafrati APS", pagina)
        self.assertIn("Pro Loco Villafrati APS", pagina)

    def test_il_browser_non_blocca_il_modulo_su_campi_nascosti(self):
        """I controlli li fa il programma e li scrive in cima in italiano:
        se li facesse il browser, si fermerebbe su un campo lontano e da
        fuori sembrerebbe che il pulsante non funzioni."""
        self.entra()
        pagina = self.cliente.get(
            "/riservato/manifestazione/nuova").get_data(as_text=True)
        self.assertIn("novalidate", pagina)
        corpo = pagina.split("<form", 1)[1].split("</form>", 1)[0]
        self.assertNotIn("required", corpo)

    def test_basta_il_nome_per_creare_una_manifestazione(self):
        from applicazione.riservato import informativa_predefinita
        self.entra()
        risposta = self.cliente.post("/riservato/manifestazione/nuova", data={
            "nome": "Festa di settembre",
            "informativa_privacy": informativa_predefinita()})
        self.assertEqual(risposta.status_code, 302)
        con = archivio.connessione()
        try:
            nuova = archivio.manifestazione_per_codice(
                con, "festa-di-settembre")
        finally:
            con.close()
        self.assertIsNotNone(nuova)
        self.assertIn("Pro Loco Villafrati APS", nuova["informativa_privacy"])


class ProvaCancellazioneDefinitiva(ProvaBase):
    """Cancellare e' l'unica cosa che non si puo' disfare: si fa in due
    tempi, e solo su iscrizioni gia' annullate."""

    PASSWORD = "proloco2026"

    def entra(self):
        self.cliente.post("/riservato/entrata",
                          data={"password": self.PASSWORD,
                                "ripetuta": self.PASSWORD})

    def numero_iscrizione(self):
        con = archivio.connessione()
        try:
            return con.execute("SELECT id FROM iscrizione").fetchone()["id"]
        finally:
            con.close()

    def righe_collegate(self, iscrizione_id):
        con = archivio.connessione()
        try:
            return con.execute(
                "SELECT COUNT(*) AS q FROM iscrizione_attivita "
                "WHERE iscrizione_id = ?", (iscrizione_id,)).fetchone()["q"]
        finally:
            con.close()

    # ------------------------------------------------------- la sicurezza

    def test_una_iscrizione_valida_non_si_cancella(self):
        self.iscrivi()
        self.entra()
        numero = self.numero_iscrizione()
        risposta = self.cliente.post("/riservato/iscrizione/%d/cancella"
                                     % numero)
        self.assertEqual(risposta.status_code, 302)
        self.assertEqual(self.quante_iscrizioni(), 1)

    def test_guardare_la_pagina_non_cancella_niente(self):
        self.iscrivi()
        self.entra()
        numero = self.numero_iscrizione()
        self.cliente.post("/riservato/iscrizione/%d/annulla" % numero)
        pagina = self.cliente.get("/riservato/iscrizione/%d/cancella"
                                  % numero).get_data(as_text=True)
        self.assertIn("non si pu", pagina)        # «non si può disfare»
        self.assertIn("Rossi", pagina)
        self.assertEqual(self.quante_iscrizioni(), 1)

    # --------------------------------------------------- la cancellazione

    def test_annullata_e_poi_cancellata_sparisce_davvero(self):
        self.iscrivi()
        self.entra()
        numero = self.numero_iscrizione()
        self.assertEqual(self.righe_collegate(numero), 1)

        self.cliente.post("/riservato/iscrizione/%d/annulla" % numero)
        risposta = self.cliente.post("/riservato/iscrizione/%d/cancella"
                                     % numero)
        self.assertEqual(risposta.status_code, 302)
        self.assertEqual(self.quante_iscrizioni(), 0)
        self.assertEqual(self.righe_collegate(numero), 0)

    def test_il_codice_di_conferma_non_apre_piu_niente(self):
        risposta = self.iscrivi()
        indirizzo = risposta.headers["Location"]
        self.entra()
        numero = self.numero_iscrizione()
        self.cliente.post("/riservato/iscrizione/%d/annulla" % numero)
        self.cliente.post("/riservato/iscrizione/%d/cancella" % numero)
        self.assertEqual(self.cliente.get(indirizzo).status_code, 404)

    def test_in_blocco_si_cancellano_solo_le_annullate(self):
        self.iscrivi(gettone="prima")
        self.iscrivi(gettone="seconda", nome="Anna")
        self.entra()
        con = archivio.connessione()
        prima = con.execute("SELECT id FROM iscrizione ORDER BY id").fetchall()
        con.close()
        self.cliente.post("/riservato/iscrizione/%d/annulla" % prima[0]["id"])

        risposta = self.cliente.post(
            "/riservato/manifestazione/%d/cancella-annullate"
            % self.manifestazione_id)
        self.assertEqual(risposta.status_code, 302)
        self.assertEqual(self.quante_iscrizioni(), 1)
        con = archivio.connessione()
        try:
            rimasta = con.execute("SELECT nome FROM iscrizione").fetchone()
        finally:
            con.close()
        self.assertEqual(rimasta["nome"], "Anna")

    def test_senza_annullate_non_propone_la_cancellazione_in_blocco(self):
        self.iscrivi()
        self.entra()
        pagina = self.cliente.get("/riservato/manifestazione/%d"
                                  % self.manifestazione_id).get_data(
                                      as_text=True)
        self.assertNotIn("cancella-annullate", pagina)

    def test_con_una_annullata_propone_la_cancellazione_in_blocco(self):
        self.iscrivi()
        self.entra()
        self.cliente.post("/riservato/iscrizione/%d/annulla"
                          % self.numero_iscrizione())
        pagina = self.cliente.get("/riservato/manifestazione/%d"
                                  % self.manifestazione_id).get_data(
                                      as_text=True)
        self.assertIn("cancella-annullate", pagina)
        self.assertIn("cancella definitivamente", pagina.lower())

    def test_i_posti_tornano_giusti_dopo_la_cancellazione(self):
        self.iscrivi(tipo="gruppo", gruppo_nome="Amici", numero_persone="4")
        self.entra()
        numero = self.numero_iscrizione()
        self.cliente.post("/riservato/iscrizione/%d/annulla" % numero)
        self.cliente.post("/riservato/iscrizione/%d/cancella" % numero)
        self.assertEqual(self.persone_su(self.pranzo), 0)
        pagina = self.cliente.get("/m/festa").get_data(as_text=True)
        self.assertIn("posti rimasti: 10 su 10", pagina)


    def test_le_annullate_si_vedono_nell_elenco(self):
        """Senza vederle non si potrebbero ne' rimettere fra le valide ne'
        cancellare: restavano invisibili e irraggiungibili."""
        self.iscrivi()
        self.entra()
        self.cliente.post("/riservato/iscrizione/%d/annulla"
                          % self.numero_iscrizione())
        pagina = self.cliente.get("/riservato/manifestazione/%d"
                                  % self.manifestazione_id).get_data(
                                      as_text=True)
        self.assertIn("Rossi", pagina)
        self.assertIn("annullata", pagina)
        self.assertIn("rimetti fra le valide", pagina)


if __name__ == "__main__":
    unittest.main()
