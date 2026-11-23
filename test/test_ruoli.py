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

    def test_chi_si_iscrive_da_solo_deve_dirlo(self):
        risposta = self.iscrivi(ruolo="")
        self.assertEqual(risposta.status_code, 400)
        self.assertIn("alla guida", risposta.get_data(as_text=True))
        self.assertEqual(self.quante_iscrizioni(), 0)

    def test_alla_guida_si_salva(self):
        self.iscrivi(ruolo="conducente")
        con = archivio.connessione()
        try:
            riga = con.execute("SELECT conducenti, passeggeri "
                               "FROM iscrizione").fetchone()
        finally:
            con.close()
        self.assertEqual((riga["conducenti"], riga["passeggeri"]), (1, 0))

    def test_passeggero_si_salva(self):
        self.iscrivi(ruolo="passeggero")
        con = archivio.connessione()
        try:
            riga = con.execute("SELECT conducenti, passeggeri "
                               "FROM iscrizione").fetchone()
        finally:
            con.close()
        self.assertEqual((riga["conducenti"], riga["passeggeri"]), (0, 1))

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
        self.iscrivi(ruolo="conducente")
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

    def test_se_si_sa_chi_e_la_casella_e_gia_segnata(self):
        self.iscrivi(ruolo="passeggero")
        self.entra()
        self.assertIn("casella segnata", self.stampa())

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
        self.iscrivi(ruolo="conducente")
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
