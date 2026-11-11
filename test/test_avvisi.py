# test_avvisi.py -- prove dell'avviso che arriva sul telefono.
#
# Due regole che queste prove tengono ferme:
#   - NESSUN NOME esce dal server dentro un avviso;
#   - se l'avviso non parte, l'iscrizione resta registrata lo stesso.

import unittest

from test_iscrizioni import ProvaBase
from applicazione import archivio, avvisi, pubblico


class ProvaAvvisoSulTelefono(ProvaBase):
    """L'avviso che fa squillare il telefono (ntfy).

    La cosa che conta: NESSUN NOME deve uscire dal server.
    """

    def setUp(self):
        super().setUp()
        self.mandati = []
        self.vero = avvisi.manda_senza_far_danni

        def finto(server, canale, titolo, messaggio, collegamento=None,
                  etichette=None):
            self.mandati.append({"server": server, "canale": canale,
                                 "titolo": titolo, "messaggio": messaggio,
                                 "collegamento": collegamento,
                                 "etichette": etichette})

        avvisi.manda_senza_far_danni = finto
        pubblico.avvisi.manda_senza_far_danni = finto

    def tearDown(self):
        avvisi.manda_senza_far_danni = self.vero
        pubblico.avvisi.manda_senza_far_danni = self.vero
        super().tearDown()

    def accendi(self, canale="iscrizioni-prova123"):
        con = archivio.connessione()
        archivio.scrivi_impostazione(con, avvisi.CHIAVE_CANALE, canale)
        con.close()

    # ------------------------------------------------------------ quando

    def test_senza_canale_non_parte_niente(self):
        self.iscrivi()
        self.assertEqual(self.mandati, [])

    def test_con_il_canale_parte_l_avviso(self):
        self.accendi()
        self.iscrivi()
        self.assertEqual(len(self.mandati), 1)
        self.assertEqual(self.mandati[0]["canale"], "iscrizioni-prova123")

    def test_niente_avviso_se_l_iscrizione_non_passa(self):
        self.accendi()
        self.iscrivi(consenso="")
        self.assertEqual(self.mandati, [])

    # --------------------------------------------- la regola della privacy

    def test_nell_avviso_non_ci_sono_nomi(self):
        self.accendi()
        self.iscrivi(tipo="gruppo", nome="Giuseppina", cognome="Lo Verde",
                     gruppo_nome="Moto Club Villafrati", numero_persone="4",
                     telefono="3351112233", note="Allergia alle noci")
        tutto = (self.mandati[0]["titolo"] + " "
                 + self.mandati[0]["messaggio"])
        for segreto in ("Giuseppina", "Lo Verde", "Moto Club Villafrati",
                        "3351112233", "Allergia"):
            self.assertNotIn(segreto, tutto,
                             "«%s» non deve uscire dal server" % segreto)

    def test_l_avviso_dice_quanti_e_su_cosa(self):
        self.accendi()
        self.iscrivi(tipo="gruppo", gruppo_nome="Amici", numero_persone="4")
        avviso = self.mandati[0]
        self.assertIn("Festa di prova", avviso["titolo"])
        self.assertIn("4 persone", avviso["messaggio"])
        self.assertIn("Pranzo", avviso["messaggio"])
        self.assertIn("Siamo in 4", avviso["messaggio"])
        self.assertIn("/riservato/manifestazione/", avviso["collegamento"])

    def test_avverte_quando_qualcosa_si_riempie(self):
        self.accendi()
        self.iscrivi(tipo="gruppo", gruppo_nome="Tutti", numero_persone="10")
        self.assertIn("al completo", self.mandati[0]["messaggio"])
        self.assertIn("warning", self.mandati[0]["etichette"])

    def test_la_lista_di_attesa_si_vede(self):
        self.accendi()
        self.iscrivi(tipo="gruppo", gruppo_nome="Comitiva",
                     numero_persone="12", accetta_attesa="1")
        self.assertIn("lista d'attesa", self.mandati[0]["messaggio"])

    # ------------------------------------------- la regola che conta di piu'

    def test_se_l_avviso_esplode_l_iscrizione_resta(self):
        def esplode(*argomenti, **parole):
            raise RuntimeError("il servizio degli avvisi non risponde")

        avvisi.manda_senza_far_danni = esplode
        pubblico.avvisi.manda_senza_far_danni = esplode

        self.accendi()
        risposta = self.iscrivi()
        self.assertEqual(risposta.status_code, 302)
        self.assertEqual(self.quante_iscrizioni(), 1)


class ProvaPaginaDegliAvvisi(ProvaBase):

    def entra(self):
        self.cliente.post("/riservato/entrata",
                          data={"password": "proloco2026",
                                "ripetuta": "proloco2026"})

    def test_la_pagina_propone_un_canale_difficile(self):
        self.entra()
        pagina = self.cliente.get("/riservato/avvisi").get_data(as_text=True)
        self.assertIn("ntfy", pagina)
        self.assertIn('name="canale"', pagina)

    def test_il_canale_si_salva(self):
        self.entra()
        self.cliente.post("/riservato/avvisi",
                          data={"canale": "iscrizioni-abc123",
                                "server": "https://ntfy.sh"})
        con = archivio.connessione()
        try:
            self.assertEqual(
                archivio.impostazione(con, avvisi.CHIAVE_CANALE),
                "iscrizioni-abc123")
        finally:
            con.close()

    def test_un_canale_scritto_male_non_si_salva(self):
        self.entra()
        self.cliente.post("/riservato/avvisi",
                          data={"canale": "ab", "server": "https://ntfy.sh"})
        con = archivio.connessione()
        try:
            self.assertFalse(archivio.impostazione(con, avvisi.CHIAVE_CANALE))
        finally:
            con.close()

    def test_il_canale_proposto_e_valido_e_non_indovinabile(self):
        import re
        proposto = avvisi.canale_nuovo()
        self.assertTrue(re.match(r"^[A-Za-z0-9_-]{6,64}$", proposto), proposto)
        self.assertNotEqual(proposto, avvisi.canale_nuovo())

    def test_si_puo_spegnere_lasciando_vuoto(self):
        self.entra()
        self.cliente.post("/riservato/avvisi",
                          data={"canale": "iscrizioni-abc123"})
        self.cliente.post("/riservato/avvisi", data={"canale": ""})
        con = archivio.connessione()
        try:
            self.assertEqual(
                archivio.impostazione(con, avvisi.CHIAVE_CANALE), "")
        finally:
            con.close()


class ProvaAvvisoDiAvvisiSpenti(ProvaBase):
    """Senza canale il programma non manda niente, ed e' giusto. Ma deve
    DIRLO, altrimenti si aspetta una notifica che non arrivera' mai."""

    def entra(self):
        self.cliente.post("/riservato/entrata",
                          data={"password": "proloco2026",
                                "ripetuta": "proloco2026"})

    def test_senza_canale_l_area_riservata_lo_dice(self):
        self.entra()
        pagina = self.cliente.get("/riservato/").get_data(as_text=True)
        self.assertIn("avvisi sul telefono sono spenti", pagina)
        self.assertIn("/riservato/avvisi", pagina)

    def test_con_il_canale_impostato_non_lo_dice_piu(self):
        self.entra()
        self.cliente.post("/riservato/avvisi",
                          data={"canale": "iscrizioni-abc123"})
        pagina = self.cliente.get("/riservato/").get_data(as_text=True)
        self.assertNotIn("avvisi sul telefono sono spenti", pagina)


class ProvaCampanella(ProvaBase):
    """Il numero delle iscrizioni arrivate da quando si e' guardato."""

    def entra(self):
        self.cliente.post("/riservato/entrata",
                          data={"password": "proloco2026",
                                "ripetuta": "proloco2026"})

    def test_le_iscrizioni_mai_guardate_contano_tutte(self):
        self.iscrivi(gettone="una")
        self.iscrivi(gettone="due", nome="Anna")
        self.entra()
        pagina = self.cliente.get("/riservato/").get_data(as_text=True)
        self.assertIn("2", pagina)
        self.assertIn("da quando hai guardato", pagina)

    def test_il_numero_compare_anche_nel_titolo_della_scheda(self):
        self.iscrivi()
        self.entra()
        pagina = self.cliente.get("/riservato/").get_data(as_text=True)
        self.assertIn("<title>(1)", pagina)

    def test_aperta_la_manifestazione_il_conto_riparte_da_zero(self):
        self.iscrivi()
        self.entra()
        prima = self.cliente.get("/riservato/manifestazione/%d"
                                 % self.manifestazione_id).get_data(
                                     as_text=True)
        self.assertIn("da quando hai guardato", prima)
        dopo = self.cliente.get("/riservato/").get_data(as_text=True)
        self.assertNotIn("da quando hai guardato", dopo)

    def test_una_nuova_iscrizione_fa_ripartire_il_conto(self):
        self.entra()
        self.cliente.get("/riservato/manifestazione/%d"
                         % self.manifestazione_id)
        self.iscrivi(gettone="dopo")
        pagina = self.cliente.get("/riservato/").get_data(as_text=True)
        self.assertIn("da quando hai guardato", pagina)

    def test_senza_niente_di_nuovo_la_campanella_non_compare(self):
        self.entra()
        pagina = self.cliente.get("/riservato/").get_data(as_text=True)
        self.assertNotIn("da quando hai guardato", pagina)
        self.assertNotIn("<title>(", pagina)


if __name__ == "__main__":
    unittest.main()
