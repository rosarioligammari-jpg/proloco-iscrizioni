# test_ruoli.py -- chi e' alla guida e chi e' passeggero.
#
# La domanda e' arrivata a iscrizioni gia' aperte, con 150 persone gia'
# dentro. La regola che queste prove tengono ferma e' una sola:
#
#   «non indicato» NON deve mai diventare «zero».
#
# Un parziale che sembra un totale e' peggio di nessun numero: si
# organizza il parcheggio per meta' delle moto che arrivano.

import unittest

from test_iscrizioni import ProvaBase
from applicazione import archivio


class ProvaDomandaNelModulo(ProvaBase):

    def riga_iscrizione(self):
        con = archivio.connessione()
        try:
            return con.execute(
                "SELECT numero_persone, conducenti, passeggeri, "
                "       nomi_partecipanti FROM iscrizione").fetchone()
        finally:
            con.close()

    def test_la_spunta_c_e_nel_modulo(self):
        pagina = self.cliente.get("/m/festa").get_data(as_text=True)
        self.assertIn('name="aggiungi_passeggero"', pagina)
        self.assertIn("Porto un passeggero", pagina)

    def test_la_spunta_non_si_vede_se_si_iscrive_un_gruppo(self):
        """Il nascondere non deve dipendere dal codice del browser: la
        pagina deve arrivare gia' giusta. Altrimenti, finche' quel codice
        non parte — o se si inceppa — la spunta resta li' a confondere."""
        # Si rimanda il modulo come gruppo, sbagliando qualcosa: cosi' la
        # pagina torna indietro con «gruppo» gia' scelto.
        risposta = self.iscrivi(tipo="gruppo", gruppo_nome="", 
                                numero_persone="4", conducenti="2",
                                passeggeri="2")
        pagina = risposta.get_data(as_text=True)
        pezzo_singolo = pagina.split('id="campi-singolo"')[0][-120:]
        pezzo_gruppo = pagina.split('id="campi-gruppo"')[0][-120:]
        self.assertNotIn("visibile", pezzo_singolo)
        self.assertIn("visibile", pezzo_gruppo)

    def test_per_chi_si_iscrive_da_solo_il_blocco_si_vede_subito(self):
        pagina = self.cliente.get("/m/festa").get_data(as_text=True)
        pezzo_singolo = pagina.split('id="campi-singolo"')[0][-120:]
        pezzo_gruppo = pagina.split('id="campi-gruppo"')[0][-120:]
        self.assertIn("visibile", pezzo_singolo)
        self.assertNotIn("visibile", pezzo_gruppo)

    def test_senza_spunta_e_una_persona_sola_alla_guida(self):
        self.iscrivi()
        riga = self.riga_iscrizione()
        self.assertEqual(riga["numero_persone"], 1)
        self.assertEqual((riga["conducenti"], riga["passeggeri"]), (1, 0))

    def test_con_il_passeggero_sono_DUE_persone(self):
        """La spunta aggiunge una persona vera: occupa un posto, mangia e
        paga la quota. Se questo numero sbaglia, sbaglia tutto il resto."""
        self.iscrivi(aggiungi_passeggero="1")
        riga = self.riga_iscrizione()
        self.assertEqual(riga["numero_persone"], 2)
        self.assertEqual((riga["conducenti"], riga["passeggeri"]), (1, 1))

    def test_con_il_passeggero_si_occupano_due_posti(self):
        self.iscrivi(aggiungi_passeggero="1")
        self.assertEqual(self.persone_su(self.pranzo), 2)
        pagina = self.cliente.get("/m/festa").get_data(as_text=True)
        self.assertIn("posti rimasti: 8 su 10", pagina)

    def test_il_nome_del_passeggero_si_conserva(self):
        self.iscrivi(aggiungi_passeggero="1", nome_passeggero="Anna Russo")
        riga = self.riga_iscrizione()
        nomi = riga["nomi_partecipanti"].splitlines()
        self.assertEqual(nomi[0], "Mario Rossi")
        self.assertEqual(nomi[1], "Anna Russo")

    def test_il_passeggero_senza_nome_si_iscrive_lo_stesso(self):
        risposta = self.iscrivi(aggiungi_passeggero="1")
        self.assertEqual(risposta.status_code, 302)
        self.assertEqual(self.riga_iscrizione()["numero_persone"], 2)

    def test_un_gruppo_divide_i_suoi(self):
        self.iscrivi(tipo="gruppo", gruppo_nome="Moto Club",
                     numero_persone="4", conducenti="2", passeggeri="2")
        con = archivio.connessione()
        try:
            riga = con.execute("SELECT conducenti, passeggeri "
                               "FROM iscrizione").fetchone()
        finally:
            con.close()
        self.assertEqual((riga["conducenti"], riga["passeggeri"]), (2, 2))

    def test_se_la_somma_non_torna_non_si_iscrive(self):
        risposta = self.iscrivi(tipo="gruppo", gruppo_nome="Moto Club",
                                numero_persone="4", conducenti="2",
                                passeggeri="1")
        self.assertEqual(risposta.status_code, 400)
        self.assertIn("devono fare 4", risposta.get_data(as_text=True))
        self.assertEqual(self.quante_iscrizioni(), 0)

    def test_un_gruppo_senza_i_due_numeri_non_passa(self):
        risposta = self.iscrivi(tipo="gruppo", gruppo_nome="Moto Club",
                                numero_persone="4", conducenti="",
                                passeggeri="")
        self.assertEqual(risposta.status_code, 400)
        self.assertEqual(self.quante_iscrizioni(), 0)

    def test_zero_alla_guida_e_un_numero_valido(self):
        # Quattro persone su un'auto al seguito: nessuno guida una moto.
        self.iscrivi(tipo="gruppo", gruppo_nome="Accompagnatori",
                     numero_persone="4", conducenti="0", passeggeri="4")
        self.assertEqual(self.quante_iscrizioni(), 1)


class ProvaINumeriSonoOnesti(ProvaBase):
    """Il cuore della faccenda: i 150 arrivati prima."""

    def vecchia_iscrizione(self, quante=3):
        """Un'iscrizione come quelle arrivate prima della domanda:
        conducenti e passeggeri restano vuoti."""
        con = archivio.connessione()
        con.execute(
            "INSERT INTO iscrizione (manifestazione_id, codice_conferma, "
            "  tipo, nome, cognome, telefono, gruppo_nome, numero_persone, "
            "  consenso_privacy, stato, creata_il) "
            "VALUES (?, 'VECCHIA1', 'gruppo', 'Carmelo', 'Vecchio', '333', "
            "        'Prima della domanda', ?, 1, 'confermata', ?)",
            (self.manifestazione_id, quante, archivio.adesso()))
        numero = con.execute("SELECT id FROM iscrizione "
                             "WHERE codice_conferma='VECCHIA1'").fetchone()["id"]
        con.execute(
            "INSERT INTO iscrizione_attivita (iscrizione_id, attivita_id, "
            "  persone, stato) VALUES (?, ?, ?, 'confermata')",
            (numero, self.passeggiata, quante))
        con.close()
        return numero

    def totali(self):
        con = archivio.connessione()
        try:
            return archivio.totali_manifestazione(con, self.manifestazione_id)
        finally:
            con.close()

    def test_chi_e_arrivato_prima_conta_fra_i_non_indicati(self):
        self.vecchia_iscrizione(quante=3)
        totali = self.totali()
        self.assertEqual(totali["conducenti"], 0)
        self.assertEqual(totali["passeggeri"], 0)
        self.assertEqual(totali["ruolo_non_indicato"], 3)

    def test_non_indicato_non_diventa_zero(self):
        """Tre vecchi e un nuovo alla guida: il totale «alla guida» deve
        essere 1, e i tre devono restare visibili come non indicati."""
        self.vecchia_iscrizione(quante=3)
        self.iscrivi()
        totali = self.totali()
        self.assertEqual(totali["conducenti"], 1)
        self.assertEqual(totali["ruolo_non_indicato"], 3)
        self.assertEqual(totali["persone"], 4)

    def test_la_scheda_avverte_che_i_numeri_sono_parziali(self):
        self.vecchia_iscrizione()
        self.cliente.post("/riservato/entrata",
                          data={"password": "proloco2026",
                                "ripetuta": "proloco2026"})
        pagina = self.cliente.get("/riservato/manifestazione/%d"
                                  % self.manifestazione_id).get_data(
                                      as_text=True)
        self.assertIn("non indicato", pagina)
        self.assertIn("sono parziali", pagina)

    def test_completati_tutti_l_avviso_sparisce(self):
        numero = self.vecchia_iscrizione(quante=3)
        self.cliente.post("/riservato/entrata",
                          data={"password": "proloco2026",
                                "ripetuta": "proloco2026"})
        self.cliente.post("/riservato/iscrizione/%d/ruoli" % numero,
                          data={"conducenti": "2", "passeggeri": "1"})
        totali = self.totali()
        self.assertEqual(totali["conducenti"], 2)
        self.assertEqual(totali["passeggeri"], 1)
        self.assertEqual(totali["ruolo_non_indicato"], 0)
        pagina = self.cliente.get("/riservato/manifestazione/%d"
                                  % self.manifestazione_id).get_data(
                                      as_text=True)
        self.assertNotIn("sono parziali", pagina)

    def test_completando_la_somma_deve_tornare(self):
        numero = self.vecchia_iscrizione(quante=3)
        self.cliente.post("/riservato/entrata",
                          data={"password": "proloco2026",
                                "ripetuta": "proloco2026"})
        self.cliente.post("/riservato/iscrizione/%d/ruoli" % numero,
                          data={"conducenti": "2", "passeggeri": "2"})
        self.assertEqual(self.totali()["ruolo_non_indicato"], 3)


class ProvaRuoloSulBiglietto(ProvaBase):

    def entra(self):
        self.cliente.post("/riservato/entrata",
                          data={"password": "proloco2026",
                                "ripetuta": "proloco2026"})

    def stampa(self):
        return self.cliente.get("/riservato/manifestazione/%d/biglietti"
                                % self.manifestazione_id).get_data(
                                    as_text=True)

    def test_le_caselline_ci_sono_sempre(self):
        self.iscrivi()
        self.entra()
        pagina = self.stampa()
        self.assertIn("alla guida", pagina)
        self.assertIn("passeggero", pagina)

    def test_chi_porta_un_passeggero_fa_due_biglietti_distinti(self):
        """Qui si sa chi e' chi: il primo biglietto e' di chi guida, il
        secondo del passeggero. Le caselline escono gia' segnate."""
        self.iscrivi(aggiungi_passeggero="1", nome_passeggero="Anna Russo")
        self.entra()
        pagina = self.stampa()
        self.assertEqual(pagina.count("casella segnata"), 2)
        self.assertIn("Mario Rossi", pagina)
        self.assertIn("Anna Russo", pagina)

    def test_in_un_gruppo_misto_le_caselline_restano_vuote(self):
        """Di un gruppo con due alla guida e due passeggeri sappiamo
        quanti, non quale biglietto sia di chi: si spunta al cancello."""
        self.iscrivi(tipo="gruppo", gruppo_nome="Moto Club",
                     numero_persone="4", conducenti="2", passeggeri="2")
        self.entra()
        self.assertNotIn("casella segnata", self.stampa())

    def test_in_un_gruppo_tutto_alla_guida_le_caselline_sono_segnate(self):
        self.iscrivi(tipo="gruppo", gruppo_nome="Moto Club",
                     numero_persone="3", conducenti="3", passeggeri="0")
        self.entra()
        self.assertEqual(self.stampa().count("casella segnata"), 3)


class ProvaEsportazione(ProvaBase):

    def test_l_excel_ha_le_due_colonne(self):
        self.iscrivi()
        self.cliente.post("/riservato/entrata",
                          data={"password": "proloco2026",
                                "ripetuta": "proloco2026"})
        testo = self.cliente.get("/riservato/manifestazione/%d/elenco.csv"
                                 % self.manifestazione_id).get_data().decode(
                                     "utf-8")
        self.assertIn("Alla guida", testo)
        self.assertIn("Passeggeri", testo)

    def test_chi_non_l_ha_detto_risulta_non_indicato_anche_nell_excel(self):
        con = archivio.connessione()
        con.execute(
            "INSERT INTO iscrizione (manifestazione_id, codice_conferma, "
            "  tipo, nome, cognome, numero_persone, consenso_privacy, "
            "  stato, creata_il) "
            "VALUES (?, 'VECCHIA2', 'singolo', 'Carmelo', 'Vecchio', 1, 1, "
            "        'confermata', ?)",
            (self.manifestazione_id, archivio.adesso()))
        con.close()
        self.cliente.post("/riservato/entrata",
                          data={"password": "proloco2026",
                                "ripetuta": "proloco2026"})
        testo = self.cliente.get("/riservato/manifestazione/%d/elenco.csv"
                                 % self.manifestazione_id).get_data().decode(
                                     "utf-8")
        self.assertIn("non indicato", testo)


if __name__ == "__main__":
    unittest.main()
