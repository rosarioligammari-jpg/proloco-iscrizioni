# test_avvisi.py -- prove dell'avviso per email agli organizzatori.
#
# La regola che conta: l'avviso e' un di piu'. Se la posta non funziona,
# l'iscrizione della persona deve restare registrata lo stesso.

import unittest
from pathlib import Path

from test_iscrizioni import ProvaBase
from applicazione import archivio, avvisi, posta, pubblico


class ProvaLetturaCasella(unittest.TestCase):
    """Il file della casella e' quello gia' in uso sul server:
    «chiave valore» separati da uno spazio, con righe di commento."""

    def scrivi(self, testo):
        import tempfile
        percorso = Path(tempfile.mkdtemp()) / "posta.conf"
        percorso.write_text(testo, encoding="utf-8")
        return str(percorso)

    def test_legge_il_formato_del_server(self):
        percorso = self.scrivi(
            "# commento\n"
            "server smtps.esempio.it\n"
            "porta 465\n"
            "casella notifiche@esempio.it\n"
            "password segretissima\n"
            "rispondi_a risposte@esempio.it\n")
        conf = posta.impostazioni(percorso)
        self.assertEqual(conf["server"], "smtps.esempio.it")
        self.assertEqual(conf["porta"], "465")
        self.assertEqual(conf["rispondi_a"], "risposte@esempio.it")

    def test_se_il_file_non_ce_lo_dice_e_si_ferma(self):
        with self.assertRaises(posta.PostaSpenta):
            posta.impostazioni("/non/esiste/posta.conf")

    def test_se_manca_una_voce_lo_dice_e_si_ferma(self):
        percorso = self.scrivi("server smtps.esempio.it\nporta 465\n")
        with self.assertRaises(posta.PostaSpenta) as caso:
            posta.impostazioni(percorso)
        self.assertIn("casella", str(caso.exception))

    def test_gli_indirizzi_si_scrivono_come_viene(self):
        atteso = ["uno@x.it", "due@y.it"]
        for scritto in ("uno@x.it, due@y.it",
                        "uno@x.it;due@y.it",
                        "uno@x.it due@y.it",
                        "uno@x.it\ndue@y.it"):
            self.assertEqual(posta.indirizzi(scritto), atteso, scritto)
        self.assertEqual(posta.indirizzi(""), [])
        self.assertEqual(posta.indirizzi("non-e-un-indirizzo"), [])


class ProvaAvvisoAllIscrizione(ProvaBase):

    def setUp(self):
        super().setUp()
        self.spediti = []
        self.vero_invio = posta.spedisci_senza_far_danni

        def finto(destinatari, oggetto, testo, percorso=None):
            self.spediti.append({"a": destinatari, "oggetto": oggetto,
                                 "testo": testo})

        posta.spedisci_senza_far_danni = finto
        pubblico.posta.spedisci_senza_far_danni = finto

    def tearDown(self):
        posta.spedisci_senza_far_danni = self.vero_invio
        pubblico.posta.spedisci_senza_far_danni = self.vero_invio
        super().tearDown()

    def chiedi_avvisi(self, indirizzi):
        con = archivio.connessione()
        con.execute("UPDATE manifestazione SET avvisi_a = ? "
                    "WHERE codice = 'festa'", (indirizzi,))
        con.close()

    # ------------------------------------------------------------ quando

    def test_senza_indirizzi_non_parte_niente(self):
        self.iscrivi()
        self.assertEqual(self.spediti, [])

    def test_con_un_indirizzo_parte_un_avviso(self):
        self.chiedi_avvisi("presidente@esempio.it")
        self.iscrivi()
        self.assertEqual(len(self.spediti), 1)
        self.assertEqual(self.spediti[0]["a"], ["presidente@esempio.it"])

    def test_a_piu_indirizzi(self):
        self.chiedi_avvisi("uno@esempio.it, due@esempio.it")
        self.iscrivi()
        self.assertEqual(self.spediti[0]["a"],
                         ["uno@esempio.it", "due@esempio.it"])

    def test_niente_avviso_se_l_iscrizione_non_passa(self):
        self.chiedi_avvisi("presidente@esempio.it")
        self.iscrivi(consenso="")
        self.assertEqual(self.spediti, [])

    # ----------------------------------------------------- cosa c'e' dentro

    def test_l_avviso_dice_chi_cosa_e_quanti_siamo(self):
        self.chiedi_avvisi("presidente@esempio.it")
        self.iscrivi(tipo="gruppo", gruppo_nome="Moto Club Villafrati",
                     numero_persone="4", note="Un bambino al pranzo.")
        testo = self.spediti[0]["testo"]
        self.assertIn("Mario Rossi", testo)
        self.assertIn("Moto Club Villafrati", testo)
        self.assertIn("Pranzo", testo)
        self.assertIn("80,00 €", testo)          # 4 x 20,00
        self.assertIn("Un bambino al pranzo.", testo)
        self.assertIn("4 persone su 1 iscrizioni", testo)
        self.assertIn("/riservato/manifestazione/", testo)

    def test_l_oggetto_si_capisce_dalla_notifica_del_telefono(self):
        self.chiedi_avvisi("presidente@esempio.it")
        self.iscrivi()
        oggetto = self.spediti[0]["oggetto"]
        self.assertIn("Nuova iscrizione", oggetto)
        self.assertIn("Festa di prova", oggetto)
        self.assertIn("Rossi", oggetto)

    def test_la_lista_di_attesa_si_vede_nell_avviso(self):
        self.chiedi_avvisi("presidente@esempio.it")
        self.iscrivi(tipo="gruppo", gruppo_nome="Comitiva",
                     numero_persone="12", accetta_attesa="1")
        self.assertIn("IN LISTA D'ATTESA", self.spediti[0]["testo"])

    # ------------------------------------------- la regola che conta di piu'

    def test_se_la_posta_e_rotta_l_iscrizione_resta(self):
        def esplode(*argomenti, **parole):
            raise RuntimeError("il server della posta non risponde")

        posta.spedisci_senza_far_danni = esplode
        pubblico.posta.spedisci_senza_far_danni = esplode

        self.chiedi_avvisi("presidente@esempio.it")
        risposta = self.iscrivi()
        self.assertEqual(risposta.status_code, 302)
        self.assertEqual(self.quante_iscrizioni(), 1)
        self.assertEqual(self.persone_su(self.pranzo), 1)


class ProvaCampoDegliAvvisi(ProvaBase):
    """L'indirizzo si scrive dall'area riservata, non nel codice."""

    def entra(self):
        self.cliente.post("/riservato/entrata",
                          data={"password": "proloco2026",
                                "ripetuta": "proloco2026"})

    def test_l_indirizzo_si_salva_dal_modulo(self):
        self.entra()
        self.cliente.post("/riservato/manifestazione/%d/modifica"
                          % self.manifestazione_id,
                          data={"nome": "Festa di prova",
                                "informativa_privacy": "Informativa.",
                                "avvisi_a": "presidente@esempio.it"})
        con = archivio.connessione()
        try:
            riga = archivio.manifestazione_per_codice(con, "festa")
        finally:
            con.close()
        self.assertEqual(riga["avvisi_a"], "presidente@esempio.it")

    def test_il_campo_compare_nel_modulo(self):
        self.entra()
        pagina = self.cliente.get(
            "/riservato/manifestazione/%d/modifica"
            % self.manifestazione_id).get_data(as_text=True)
        self.assertIn('name="avvisi_a"', pagina)

    def test_duplicando_si_portano_dietro_gli_indirizzi(self):
        con = archivio.connessione()
        con.execute("UPDATE manifestazione SET avvisi_a = 'presidente@esempio.it' "
                    "WHERE codice = 'festa'")
        con.close()
        self.entra()
        self.cliente.post("/riservato/manifestazione/%d/duplica"
                          % self.manifestazione_id)
        con = archivio.connessione()
        try:
            copia = archivio.manifestazione_per_codice(
                con, "festa-di-prova-copia")
        finally:
            con.close()
        self.assertEqual(copia["avvisi_a"], "presidente@esempio.it")


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


if __name__ == "__main__":
    unittest.main()
