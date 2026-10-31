# Contenitore del programma Iscrizioni, nella stessa forma degli altri
# programmi dello studio sul server.

FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ISCRIZIONI_CARTELLA_DATI=/dati \
    ISCRIZIONI_INDIRIZZO=0.0.0.0 \
    ISCRIZIONI_PORTA=8000

WORKDIR /app

COPY requisiti.txt .
RUN pip install --no-cache-dir -r requisiti.txt

COPY . .

# Utente senza privilegi: il programma non gira da root.
# Il numero 10001 e' lo stesso usato dagli altri programmi dello studio,
# cosi' la cartella dei dati sul server ha gia' i permessi giusti.
RUN useradd --create-home --uid 10001 iscrizioni \
 && mkdir -p /dati \
 && chown -R iscrizioni:iscrizioni /app /dati
USER iscrizioni

EXPOSE 8000

CMD ["python", "avvia.py"]
