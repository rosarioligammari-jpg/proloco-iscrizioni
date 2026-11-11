# test_biglietti.py -- prove dei biglietti da stampare.
#
# Il numero sul biglietto e' quello che al banco permette di dire «il 47
# ha gia' ritirato»: non si deve ripetere mai, nemmeno fra gli iscritti e
# i biglietti in bianco.

import re
import unittest

from test_iscrizioni import ProvaBase
from applicazione import archivio


class ProvaBiglietti(ProvaBase):

    def entra(self):
        self.cliente.post("/riservato/entrata",
                          data={"password": "proloco2026",
                                "ripetuta": "proloco2026"})

    def stampa(self, **parametri):
        pezzi = "&".join("%s=%s" % (c, v) for c, v in parametri.items())
        indirizzo = "/riservato/manifestazione/%d/biglietti" % (
            self.manifestazione_id)
        if pezzi:
            indirizzo += "?" + pezzi
        return self.cliente.get(indirizzo).get_data(as_text=True)

    def numeri(self, pagina):
        return [int(n) for n in
                re.findall(r'class="biglietto-numero">(\d+)<', pagina)]

    # --------------------------------------------- uno per ogni persona

    def test_una_persona_un_biglietto(self):
        self.iscrivi()
        self.entra()
        self.assertEqual(self.numeri(self.stampa()), [1])

    def test_un_gruppo_di_quattro_fa_quattro_biglietti(self):
        self.iscrivi(tipo="gruppo", gruppo_nome="Moto Club",
                     numero_persone="4")
        self.entra()
        self.assertEqual(self.numeri(self.stampa()), [1, 2, 3, 4])

    def test_i_nomi_del_gruppo_finiscono_sui_biglietti(self):
        self.iscrivi(tipo="gruppo", gruppo_nome="Moto Club",
                     numero_persone="3",
                     nomi_partecipanti="Giuseppe Lo Verde\nAnna Russo\nCarlo Neri")
        self.entra()
        pagina = self.stampa()
        for nome in ("Giuseppe Lo Verde", "Anna Russo", "Carlo Neri"):
            self.assertIn(nome, pagina)

    def test_senza_i_nomi_il_primo_biglietto_porta_il_referente(self):
        self.iscrivi(tipo="gruppo", gruppo_nome="Amici", numero_persone="3")
        self.entra()
        pagina = self.stampa()
        self.assertIn("Mario Rossi", pagina)
        self.assertIn("1 di 3", pagina)
        self.assertIn("3 di 3", pagina)

    # -------------------------------------------------- i numeri in fila

    def test_i_numeri_non_si_ripetono_mai(self):
        self.iscrivi(gettone="a")
        self.iscrivi(gettone="b", tipo="gruppo", gruppo_nome="Amici",
                     numero_persone="3")
        self.entra()
        numeri = self.numeri(self.stampa(bianchi=5))
        self.assertEqual(numeri, list(range(1, 10)))
        self.assertEqual(len(numeri), len(set(numeri)))

    def test_i_bianchi_continuano_la_numerazione(self):
        self.iscrivi()
        self.entra()
        self.assertEqual(self.numeri(self.stampa(bianchi=3)), [1, 2, 3, 4])

    def test_senza_bianchi_ci_sono_solo_gli_iscritti(self):
        self.iscrivi()
        self.entra()
        self.assertEqual(self.numeri(self.stampa()), [1])

    # ------------------------------------------------------- chi entra

    def test_un_iscrizione_annullata_non_fa_biglietto(self):
        self.iscrivi()
        self.entra()
        con = archivio.connessione()
        numero = con.execute("SELECT id FROM iscrizione").fetchone()["id"]
        con.close()
        self.cliente.post("/riservato/iscrizione/%d/annulla" % numero)
        self.assertEqual(self.numeri(self.stampa()), [])

    def test_si_puo_stampare_solo_per_una_attivita(self):
        self.iscrivi(gettone="pranzo", attivita=[str(self.pranzo)])
        self.iscrivi(gettone="passeggiata", nome="Anna",
                     attivita=[str(self.passeggiata)])
        self.entra()
        solo_pranzo = self.stampa(attivita=self.pranzo)
        self.assertIn("Mario Rossi", solo_pranzo)
        self.assertNotIn("Anna", solo_pranzo)
        self.assertEqual(len(self.numeri(solo_pranzo)), 1)

    # --------------------------------------------------- cosa c'e' sopra

    def test_i_tagliandi_sono_quelli_chiesti(self):
        self.iscrivi()
        self.entra()
        pagina = self.stampa(tagliandi="Pasto,%20Bibita,%20Gadget")
        for tagliando in ("Pasto", "Bibita", "Gadget"):
            self.assertIn(">%s<" % tagliando, pagina)

    def test_sul_biglietto_c_e_il_nome_della_manifestazione(self):
        self.iscrivi()
        self.entra()
        self.assertIn("Festa di prova", self.stampa())

    def test_senza_iscritti_lo_dice_invece_di_dare_un_foglio_vuoto(self):
        self.entra()
        self.assertIn("niente da stampare", self.stampa())


if __name__ == "__main__":
    unittest.main()
