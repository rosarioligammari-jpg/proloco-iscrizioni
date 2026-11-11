# Iscrizioni — Pro Loco Villafrati APS

Programma per raccogliere le iscrizioni alle manifestazioni. Si manda un
**link** nei gruppi, le persone si iscrivono dal telefono, e tu vedi in ogni
momento **quanti saremo**.

Vale per **tutte** le manifestazioni, non solo per il Motor Village Fest:
ogni manifestazione ha le sue attività, i suoi posti, le sue quote e il suo
link.

---

## Come si avvia

Su **Windows**: doppio clic su `Avvia Iscrizioni.bat`.
Su **Mac**: doppio clic su `Avvia Iscrizioni.command`.
Su **Linux**: `./avvia_linux.sh` (sul server dell'ufficio parte da solo,
vedi `docs/PUBBLICAZIONE.md`).

Si apre una finestra nera che resta aperta: è il programma in funzione.
Nella finestra compaiono gli indirizzi da aprire nel browser. Per fermarlo si
chiude la finestra.

Da riga di comando, dentro la cartella del programma:

```bash
python avvia.py
```

Il programma usa la **porta 5021**. Le porte degli altri programmi non si
toccano: 5001 ELMO, 5011 DVR, 5012 PSC, 5013 POS.

### Le librerie che servono

```bash
pip install -r requisiti.txt
```

Sono due, tutte e due in puro Python: **Flask** (le pagine) e **waitress**
(il server). Se `waitress` manca, il programma parte lo stesso con il
server di prova di Flask e lo scrive nella finestra nera: va bene per
lavorare, **non** per stare su internet.

### Metterlo su internet

Tutto in **`docs/PUBBLICAZIONE.md`**: comandi uno per riga per il PC Linux
dell'ufficio, il servizio che lo tiene sempre acceso, la copia di sicurezza
ogni notte e le due strade per farlo raggiungere da fuori.

---

## Gli indirizzi

| Pagina | Indirizzo |
|---|---|
| elenco delle manifestazioni | `http://127.0.0.1:5021/` |
| pagina di iscrizione | `http://127.0.0.1:5021/m/<codice>` |
| conferma dell'iscritto | `http://127.0.0.1:5021/m/<codice>/iscritto/<codice>` |
| **area riservata** | `http://127.0.0.1:5021/riservato/` |

Dallo stesso computer vale `127.0.0.1`; da un telefono collegato alla stessa
rete vale l'altro indirizzo scritto nella finestra nera (quello che comincia
con `192.168.`).

---

## L'area riservata

È la parte degli organizzatori: `http://127.0.0.1:5021/riservato/`.

**La prima volta che la apri scegli tu la password.** Scrivila da qualche
parte: in archivio non viene conservata in chiaro e non si recupera. Dopo
cinque tentativi sbagliati il programma si blocca per dieci minuti.

Da lì si fa tutto, senza toccare il codice:

| Cosa | Dove |
|---|---|
| creare una manifestazione | «Nuova manifestazione» |
| aggiungere attività, con posti e quota | nella scheda della manifestazione |
| cambiare posti, orari, quote | «modifica» accanto all'attività |
| togliere un'attività dal modulo | «sospendi» (non si cancella, si spegne) |
| chiudere o riaprire le iscrizioni | «Chiudi le iscrizioni» |
| rifare la stessa manifestazione l'anno dopo | «Duplica per un'altra volta» |
| vedere **quanti saremo** e le quote attese | in cima alla scheda |
| dare il posto a chi è in lista d'attesa | «dagli il posto» accanto alla riga |
| annullare un'iscrizione sbagliata | «annulla» (resta in archivio) |
| scaricare l'elenco per Excel | «Scarica l'elenco per Excel» |
| copiare il link da mandare nei gruppi | «Copia il link» |

Due cose che il programma **non** fa, di proposito:

- **non cancella niente per sbaglio.** Un'iscrizione sbagliata si *annulla*
  e resta in archivio; un'attività che non si fa più si *sospende*. Da lì si
  torna sempre indietro. Per far sparire davvero un'iscrizione ci vuole un
  **secondo gesto**: vedi qui sotto.
- **non incassa.** Le quote si pagano in loco: il programma dice solo quanto
  ci si aspetta di incassare.

### Il «duplica»

Copia nome, descrizione, informativa, attività, posti e quote. **Non** copia
gli iscritti e **non** copia le date, e la copia nasce con le **iscrizioni
chiuse**: così si correggono con calma nome e date prima di riaprire.

---

## Cancellare davvero un'iscrizione

Si fa in **due tempi**, perché è l'unica cosa del programma che non si può
disfare:

1. l'iscrizione si **annulla** (resta in archivio, in grigio, non conta nei
   totali e non occupa posti);
2. sull'iscrizione annullata compare **«cancella definitivamente»**, che
   porta a una pagina di conferma dove c'è scritto esattamente cosa
   sparisce. Solo lì si cancella davvero.

C'è anche il pulsante **«Cancella definitivamente le N annullate»**, per
fare pulizia in blocco a manifestazione finita.

Dopo la cancellazione il file dell'archivio viene **riscritto**: il testo
cancellato non resta dentro il file. Chi chiede che i suoi dati spariscano
ha diritto che spariscano davvero.

**Quando è giusto cancellare**

- **qualcuno chiede che i suoi dati siano cancellati**: è un suo diritto,
  scritto nell'informativa che ha firmato;
- **la manifestazione è finita** e si fa pulizia.

Se invece serve solo tenerla fuori dai conti, basta lasciarla *annullata*.

---

## Il logo

Il logo è **già a posto**: in `applicazione/static/` ci sono

| file | quale versione |
|---|---|
| `logo.png` | quella per **sfondo scuro** (scritte bianche): è quella in testata |
| `logo_sfondo_chiaro.png` | quella per **sfondo chiaro** (scritte nere), pronta per le stampe |

Vengono dal PDF `Logo Proloco Villafrati vuoto.pdf`, ritagliate al vivo e
portate a 480 × 480 punti. La testata del sito usa il **blu del logo**
(`#2b384b`), così l'immagine ci si fonde dentro senza riquadri.

Per cambiarlo basta sostituire `logo.png` (vanno bene anche `.svg`, `.jpg`,
`.webp`). Se il file manca, le pagine funzionano lo stesso con la sola
intestazione di testo: per il logo il programma non si ferma mai.

---

## I dati di prova

Per vedere il programma all'opera c'è una manifestazione **inventata**:

```bash
python "dati_prova\carica_prova.py"
```

Carica un «Motor Village Fest» con otto attività: **nomi, orari, posti e
quote sono inventati** e vanno sostituiti con quelli veri.

---

## Le prove automatiche

Dopo ogni modifica, dentro la cartella del programma:

```bash
python -m unittest discover -s test -v
```

Devono passare tutte. Controllano i posti, i gruppi, la lista d'attesa, il
doppio clic, la chiusura delle iscrizioni e gli accenti nelle pagine.

---

## L'avviso sul telefono

Area riservata → **«Avvisi sul telefono»**. Ogni volta che qualcuno si
iscrive, il telefono squilla con un avviso tipo:

> **Motor Village Fest · nuova iscrizione**
> 4 persone · Pranzo sociale, Gimkana a tempo
> Siamo in 37, su 12 iscrizioni.

Toccandolo si apre l'elenco completo nell'area riservata.

### Come si imposta, una volta sola

1. sul telefono si installa l'app gratuita **ntfy** (App Store o Play Store);
2. nella pagina «Avvisi sul telefono» si salva il **nome del canale** (ce
   n'è già uno pronto, con dentro una parte casuale);
3. nell'app si tocca **«+»** e si scrive **lo stesso nome**, identico;
4. si torna nella pagina e si preme **«Manda un avviso di prova»**.

Il nome del canale è l'unica cosa che protegge gli avvisi: chi lo conosce
li riceve. Non va scritto in pubblico. Per cambiarlo basta salvarne uno
nuovo e rifare il passo 3.

### L'inciampo da conoscere: il servizio

Di app chiamate «ntfy» ne esistono diverse, e **non usano tutte lo stesso
servizio**: alcune lavorano su `ntfy.sh`, altre su `ntfy-me.com`, altre
ancora su indirizzi propri. Se il servizio scritto nella pagina «Avvisi sul
telefono» è diverso da quello dell'app, **gli avvisi partono e nessuno li
riceve, senza che niente dia errore** da nessuna delle due parti.

Per sapere quale usa l'app: aprirla, entrare nel canale e guardare
l'indirizzo completo che mostra — `https://qualcosa.com/nome-del-canale`.
La parte prima della barra è il servizio, e va copiata nella pagina.

> Successe il 02/11/2026: tutto impostato giusto, il canale uguale, e
> nessuna notifica. Il programma imbucava su `ntfy.sh`, l'app guardava su
> `ntfy-me.com`.

### Perché nell'avviso non ci sono i nomi

Chi si iscrive firma un'informativa che dice che **i suoi dati non vengono
comunicati a terzi**. Se nell'avviso mettessimo nome e telefono, quei dati
passerebbero dai server del servizio di notifica e quella frase non sarebbe
più vera. L'avviso dice quindi **quante** persone e **su cosa**, mai
**chi**: i nomi restano sul server, dietro la password, a un tocco di
distanza.

Se l'avviso non parte, **l'iscrizione resta registrata lo stesso**: il
motivo si legge con `sudo docker logs --tail 50 iscrizioni-reale`.

---

## Le difese per quando sta su internet

| Difesa | Che cosa fa |
|---|---|
| campo-trappola nel modulo | una persona non lo vede; i programmi automatici lo riempiono e l'iscrizione viene rifiutata |
| freno sugli invii | al massimo **20 iscrizioni al minuto** dallo stesso collegamento |
| limite alla dimensione | un invio più grande di mezzo megabyte viene rifiutato |
| cookie dell'area riservata | mai leggibile dal JavaScript, mai mandato ad altri siti, e solo cifrato quando `COLLEGAMENTO_SICURO` è acceso |
| password dell'area riservata | conservata come impronta, mai in chiaro; cinque tentativi sbagliati e si blocca per dieci minuti |

Il freno è volutamente **largo**: dietro lo stesso indirizzo possono esserci
tante persone diverse (una famiglia sulla stessa rete di casa, o molti
utenti dello stesso gestore telefonico). Stringerlo bloccherebbe gente in
buona fede appena il link gira nei gruppi.

---

## Dove stanno i dati

Tutto in `dati/iscrizioni.sqlite`. È un unico file: per fare una copia di
sicurezza basta copiarlo (a programma fermo). Nella stessa cartella c'è
`chiave_segreta.txt`, generato al primo avvio: non va cancellato né messo in
giro.

---

## Com'è fatto dentro

| Cartella / file | A cosa serve |
|---|---|
| `configurazione.py` | porta, nomi, percorsi: tutte le impostazioni in un punto solo |
| `avvia.py` | avvio del server |
| `applicazione/archivio.py` | il database e i conteggi dei posti |
| `applicazione/pubblico.py` | le pagine che vedono i partecipanti |
| `applicazione/formato.py` | date in `gg/mm/aaaa` e importi in euro |
| `applicazione/templates/` | le pagine |
| `applicazione/static/stile.css` | l'unico foglio di stile |
| `dati_prova/` | la manifestazione finta per le prove |
| `test/` | le prove automatiche |
| `servizio/` | il file di servizio per Linux e la copia di sicurezza |
| `docs/PUBBLICAZIONE.md` | come metterlo su internet, passo per passo |
| `requisiti.txt` | le librerie da installare |

Stesse regole degli altri programmi dello studio: Python + Flask + SQLite,
percorsi con `pathlib`, file di testo in `utf-8`, date ISO in archivio e
`gg/mm/aaaa` a schermo, nomi di file tutti minuscoli.
