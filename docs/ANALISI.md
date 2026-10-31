# Analisi — programma «Iscrizioni» della Pro Loco Villafrati APS

Scritta il 31/10/2026, prima del codice.

## 1. Il problema

La Pro Loco organizza manifestazioni (la prima è il **Motor Village Fest**)
in cui serve sapere **quanti saremo**, attività per attività: il pranzo ha i
coperti contati, la gimkana ha le batterie, il giro turistico ha un numero
massimo di mezzi. Oggi le adesioni arrivano nei gruppi di messaggistica e
contarle è un lavoro a mano che sbaglia.

Serve un modulo da **mandare come link nei gruppi**, compilabile **dal
telefono**, che tenga il conto da solo.

## 2. Vincoli decisi con l'utente

| | Scelta |
|---|---|
| chi compila | il **singolo partecipante** oppure un **capogruppo** per più persone |
| posti | **limitati per singola attività**, con lista d'attesa |
| quota | **per alcune manifestazioni sì, per altre no**: si accende attività per attività |
| strada tecnica | programma **nostro**, come ELMO e Gestione Mezzi: Python + Flask + SQLite, si usa dal browser |
| riuso | **versatile per tutte le manifestazioni future**, non solo per il Motor Village Fest |
| intestazione | **logo della Pro Loco Villafrati APS** sempre presente |
| tempi | meno di due settimane al Motor Village Fest |

## 3. Le entità

```
manifestazione  1 ──< attivita
       │                  │
       └──< iscrizione ──< iscrizione_attivita >── attivita
```

- **manifestazione**: nome, date, luogo, descrizione, informativa privacy,
  apertura/chiusura delle iscrizioni, lista d'attesa sì/no, e un **codice**
  che diventa l'indirizzo del link (`/m/motor-village-fest`);
- **attivita**: nome, giorno, ora, **posti** (vuoto = nessun limite),
  **quota in centesimi** (zero = gratuita);
- **iscrizione**: chi si è iscritto, se da solo o come gruppo, con quante
  persone, il contatto, le note, il consenso e un **codice di conferma**;
- **iscrizione_attivita**: la riga che collega un'iscrizione a un'attività,
  con **quante persone** e lo stato (`confermata` o `attesa`).

Il conteggio dei posti **non si conserva**: si ricava sempre sommando le
righe confermate. Un numero conservato è un numero che prima o poi mente.

## 4. Le regole che il programma applica

1. **Nessuna iscrizione a metà.** Se anche una sola attività scelta non ha
   posto per tutto il gruppo, non si salva niente e si spiega che cosa non
   ci sta, con i posti davvero rimasti.
2. **La lista d'attesa è una scelta esplicita** dell'iscritto: la spunta
   «mettimi in lista d'attesa» esiste solo se la manifestazione la prevede.
3. **I posti si ricontano al momento del salvataggio**, dentro una
   transazione: due persone che inviano nello stesso istante non possono
   prendere lo stesso ultimo posto.
4. **Il doppio clic non raddoppia niente.** Ogni modulo porta un gettone
   unico: il secondo invio dello stesso gettone riporta alla conferma già
   fatta invece di creare una seconda iscrizione.
5. **Quello che è stato scritto non si perde**: se manca un dato, il modulo
   torna indietro con dentro tutto quello che l'utente aveva già messo.
6. **Le iscrizioni si chiudono** o a mano o alla data stabilita; a
   iscrizioni chiuse la pagina lo dice e mostra comunque il programma.

## 5. Privacy

Si raccolgono nome, cognome, telefono, eventuale email, i nomi dei
partecipanti del gruppo e le note. Sono dati di persone fisiche: il modulo
porta l'**informativa** (chi raccoglie, per quale scopo, per quanto tempo, a
chi chiedere la cancellazione) e una **spunta di consenso obbligatoria**.
L'informativa è scritta **per ogni manifestazione**, così resta vera.

Non si raccolgono dati sanitari. Le allergie eventualmente scritte nelle
note dall'interessato sono una sua comunicazione volontaria
all'organizzatore, non un dato richiesto dal modulo.

## 6. Interfaccia

Prima il telefono: una colonna, bersagli grandi, caratteri leggibili.
I colori dicono la stessa cosa delle parole, mai solo il colore:

| | |
|---|---|
| verde | posti liberi |
| arancione | restano 5 posti o meno, oppure lista d'attesa |
| rosso | al completo, oppure manca un dato obbligatorio |

## 7. Che cosa resta fuori

**Blocco 1 (31/10/2026):** pagina pubblica di iscrizione, posti, gruppi,
lista d'attesa, quote, informativa e consenso.

**Blocco 2 (31/10/2026):** area riservata — password scelta al primo
accesso, creazione e modifica di manifestazioni e attività da schermo,
apertura e chiusura delle iscrizioni, duplicazione, totali, gestione della
lista d'attesa, annullamento di un'iscrizione, esportazione per Excel.

**Blocco 3 (31/10/2026):** preparazione alla pubblicazione — server
`waitress` al posto di quello di prova, cookie sicuri dietro `https`,
lettura dell'indirizzo vero dietro un tunnel, campo-trappola e freno sugli
invii, file di servizio per Linux, copia di sicurezza notturna e le
istruzioni passo per passo in `docs/PUBBLICAZIONE.md`.

Resta fuori:

- la **pubblicazione vera e propria**, che va fatta sul PC Linux
  dell'ufficio seguendo `docs/PUBBLICAZIONE.md`: finché non è fatta, il
  link funziona solo in rete locale;
- la stampa dell'elenco dei partecipanti e dei cartellini;
- l'avviso automatico a chi è in lista d'attesa quando si libera un posto
  (oggi il programma dice che si è liberato, l'avviso lo dà una persona);
- il **codice QR** del link, comodo sulle locandine.

## 8. Dove si è scelto al posto dell'utente

- **Nomi, posti e quote** delle otto attività del Motor Village Fest sono
  **inventati**: servivano per far funzionare le prove. Vanno sostituiti.
- Il **massimo per iscrizione di gruppo** è stato messo a **60 persone**.
- Il codice di conferma è di **8 caratteri**, senza le lettere e le cifre
  che si confondono (`O`/`0`, `I`/`1`).
- La **data della manifestazione di prova** è il 14-15 novembre 2026, con
  chiusura delle iscrizioni il 10: messa lì solo per provare la chiusura.
