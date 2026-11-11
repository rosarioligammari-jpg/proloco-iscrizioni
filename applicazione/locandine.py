# locandine.py -- l'immagine della locandina di una manifestazione.
#
# Serve a far riconoscere al volo i biglietti: sul biglietto la locandina
# compare in una banda stretta sul lato, mentre il numero e i tagliandi
# restano puliti e leggibili.
#
# Il file sta FUORI dal codice, in dati/locandine/: come l'archivio, e'
# roba dell'installazione, non del programma. Su GitHub non ci va.

from configurazione import CARTELLA_DATI, DIMENSIONE_MASSIMA_LOCANDINA

CARTELLA = "locandine"

# Che cosa accettiamo, e come si riconosce guardando i primi byte del
# file invece di fidarsi del nome: un file chiamato «foto.png» puo'
# contenere qualunque cosa.
FIRME = (
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
)


class LocandinaRifiutata(Exception):
    """Il file non va bene, e si sa perche'."""


def cartella():
    percorso = CARTELLA_DATI / CARTELLA
    percorso.mkdir(parents=True, exist_ok=True)
    return percorso


def percorso(manifestazione_id):
    """Il file della locandina, se c'e'. Altrimenti None."""
    for estensione in ("png", "jpg", "gif", "webp"):
        candidato = cartella() / ("%d.%s" % (manifestazione_id, estensione))
        if candidato.exists():
            return candidato
    return None


def _tipo_vero(contenuto):
    """Guarda i primi byte e dice che immagine e'. None se non lo e'."""
    for firma, estensione in FIRME:
        if contenuto.startswith(firma):
            return estensione
    # WEBP: «RIFF» ....  «WEBP»
    if contenuto[:4] == b"RIFF" and contenuto[8:12] == b"WEBP":
        return "webp"
    return None


def salva(manifestazione_id, contenuto):
    """Mette da parte la locandina. Alza LocandinaRifiutata se non va."""
    if not contenuto:
        raise LocandinaRifiutata("Il file è vuoto.")
    if len(contenuto) > DIMENSIONE_MASSIMA_LOCANDINA:
        raise LocandinaRifiutata(
            "L'immagine è troppo grande (%.1f MB): il limite è %.0f MB."
            % (len(contenuto) / 1048576.0,
               DIMENSIONE_MASSIMA_LOCANDINA / 1048576.0))

    estensione = _tipo_vero(contenuto)
    if estensione is None:
        raise LocandinaRifiutata(
            "Questo file non è un'immagine. Vanno bene PNG, JPG, GIF e WEBP.")

    togli(manifestazione_id)
    destinazione = cartella() / ("%d.%s" % (manifestazione_id, estensione))
    destinazione.write_bytes(contenuto)
    return destinazione


def togli(manifestazione_id):
    """Toglie la locandina. Non tocca niente altro."""
    vecchia = percorso(manifestazione_id)
    if vecchia is not None:
        vecchia.unlink()
        return True
    return False


def tipo_per_il_browser(file_locandina):
    estensione = file_locandina.suffix.lstrip(".").lower()
    return {"png": "image/png", "jpg": "image/jpeg", "gif": "image/gif",
            "webp": "image/webp"}.get(estensione, "application/octet-stream")
