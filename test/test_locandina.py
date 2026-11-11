# test_locandina.py -- prove della locandina sui biglietti.
#
# La locandina si carica dall'area riservata e finisce come banda sul
# lato del biglietto. Due cose che queste prove tengono ferme:
#   - un file che NON e' un'immagine non entra, per quanto si chiami .png;
#   - una locandina rifiutata non fa perdere le modifiche appena scritte.

import io
import unittest

from test_iscrizioni import ProvaBase
from applicazione import locandine

# Un PNG finto ma con la firma giusta: alle prove serve che i primi byte
# siano quelli di un PNG, non che l'immagine sia bella.
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
JPG = b"\xff\xd8\xff" + b"\x00" * 200
NON_IMMAGINE = b"Questo e' un foglio di testo, non una locandina."


class ProvaLocandina(ProvaBase):

    def entra(self):
        self.cliente.post("/riservato/entrata",
                          data={"password": "proloco2026",
                                "ripetuta": "proloco2026"})

    def carica(self, contenuto, nome_file="locandina.png", nome="Festa di prova"):
        return self.cliente.post(
            "/riservato/manifestazione/%d/modifica" % self.manifestazione_id,
            data={"nome": nome,
                  "informativa_privacy": "Informativa.",
                  "locandina": (io.BytesIO(contenuto), nome_file)},
            content_type="multipart/form-data")

    # -------------------------------------------------------- caricamento

    def test_un_png_si_carica(self):
        self.entra()
        self.carica(PNG)
        self.assertIsNotNone(locandine.percorso(self.manifestazione_id))

    def test_anche_un_jpg(self):
        self.entra()
        self.carica(JPG, "locandina.jpg")
        percorso = locandine.percorso(self.manifestazione_id)
        self.assertIsNotNone(percorso)
        self.assertEqual(percorso.suffix, ".jpg")

    def test_un_file_che_non_e_un_immagine_non_entra(self):
        self.entra()
        risposta = self.carica(NON_IMMAGINE, "finta.png")
        self.assertIsNone(locandine.percorso(self.manifestazione_id))
        pagina = self.cliente.get("/riservato/manifestazione/%d"
                                  % self.manifestazione_id).get_data(
                                      as_text=True)
        self.assertIn("non è un", pagina)

    def test_una_locandina_rifiutata_non_fa_perdere_le_modifiche(self):
        self.entra()
        self.carica(NON_IMMAGINE, "finta.png", nome="Nome cambiato")
        from applicazione import archivio
        con = archivio.connessione()
        try:
            riga = archivio.manifestazione_per_id(con, self.manifestazione_id)
        finally:
            con.close()
        self.assertEqual(riga["nome"], "Nome cambiato")

    def test_troppo_grande_non_entra(self):
        from configurazione import DIMENSIONE_MASSIMA_LOCANDINA
        enorme = b"\x89PNG\r\n\x1a\n" + b"\x00" * DIMENSIONE_MASSIMA_LOCANDINA
        with self.assertRaises(locandine.LocandinaRifiutata) as caso:
            locandine.salva(self.manifestazione_id, enorme)
        self.assertIn("troppo grande", str(caso.exception))

    def test_caricarne_una_nuova_sostituisce_la_vecchia(self):
        self.entra()
        self.carica(PNG)
        self.carica(JPG, "altra.jpg")
        percorso = locandine.percorso(self.manifestazione_id)
        self.assertEqual(percorso.suffix, ".jpg")
        cartella = locandine.cartella()
        quante = len(list(cartella.glob("%d.*" % self.manifestazione_id)))
        self.assertEqual(quante, 1, "deve restarne una sola")

    # ------------------------------------------------- sul biglietto

    def test_senza_locandina_i_biglietti_lo_dicono(self):
        self.iscrivi()
        self.entra()
        pagina = self.cliente.get(
            "/riservato/manifestazione/%d/biglietti"
            % self.manifestazione_id).get_data(as_text=True)
        self.assertIn("Nessuna locandina caricata", pagina)
        self.assertNotIn("biglietto-banda", pagina)

    def test_con_la_locandina_il_biglietto_ha_la_banda(self):
        self.iscrivi()
        self.entra()
        self.carica(PNG)
        pagina = self.cliente.get(
            "/riservato/manifestazione/%d/biglietti"
            % self.manifestazione_id).get_data(as_text=True)
        self.assertIn("biglietto-banda", pagina)
        self.assertIn("con-banda", pagina)
        self.assertNotIn("Nessuna locandina caricata", pagina)

    # ------------------------------------------------------ e si toglie

    def test_si_puo_togliere(self):
        self.entra()
        self.carica(PNG)
        self.cliente.post("/riservato/manifestazione/%d/locandina/togli"
                          % self.manifestazione_id)
        self.assertIsNone(locandine.percorso(self.manifestazione_id))

    def test_togliere_non_tocca_la_manifestazione(self):
        self.entra()
        self.carica(PNG)
        self.cliente.post("/riservato/manifestazione/%d/locandina/togli"
                          % self.manifestazione_id)
        from applicazione import archivio
        con = archivio.connessione()
        try:
            self.assertIsNotNone(
                archivio.manifestazione_per_id(con, self.manifestazione_id))
        finally:
            con.close()

    # ----------------------------------------------------- sta al riparo

    def test_la_locandina_sta_dietro_la_password(self):
        self.entra()
        self.carica(PNG)
        self.cliente.post("/riservato/uscita")
        risposta = self.cliente.get("/riservato/manifestazione/%d/locandina"
                                    % self.manifestazione_id)
        self.assertEqual(risposta.status_code, 302)

    def test_senza_locandina_l_indirizzo_non_inventa_niente(self):
        self.entra()
        risposta = self.cliente.get("/riservato/manifestazione/%d/locandina"
                                    % self.manifestazione_id)
        self.assertEqual(risposta.status_code, 404)


if __name__ == "__main__":
    unittest.main()
