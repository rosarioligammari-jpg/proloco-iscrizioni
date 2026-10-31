# Mettere le Iscrizioni sul server dello studio

Istruzioni per pubblicare il programma su **`https://iscrizioni.clerm.it`**,
seguendo la stessa forma degli altri programmi già in funzione sul server.

I comandi sono **uno per riga**: si copiano e si incollano, uno alla volta.
Sotto ognuno c'è scritto **cosa deve comparire** se è andata bene.

> **Niente da comprare e niente da spostare.** Il tunnel (`cloudflared`), il
> dominio `clerm.it` su Cloudflare e il comando `aggiorna` ci sono già e
> funzionano: questo programma si infila accanto agli altri.

---

## Quello che è stato deciso

| Cosa | Valore |
|---|---|
| nome nel sistema | `iscrizioni` |
| indirizzo pubblico | `https://iscrizioni.clerm.it` |
| porta del programma vero | `127.0.0.1:8113` |
| porta della copia di prova | `127.0.0.1:8213` |
| codice | `/srv/app/iscrizioni/prod` e `/srv/app/iscrizioni/test` |
| **dati** (fuori dal codice) | `/srv/app-dati/iscrizioni/prod` e `.../test` |
| contenitori | `iscrizioni-reale` e `iscrizioni-prova` |
| pagina di controllo | `/salute` |

Il server è **Debian 13**, con 90 GB liberi. Le porte 8113 e 8213 sono state
verificate libere.

---

## Passo 1 — il codice su GitHub

Il comando `aggiorna` scarica da GitHub: serve un deposito, come per gli
altri programmi.

**1.1** Su GitHub crea un deposito nuovo, **privato**, di nome
`proloco-iscrizioni`. Non aggiungere né README né licenza: deve nascere
vuoto.

**1.2** Dal PC di Windows, dentro la cartella del programma:

```bash
cd "C:\Users\PC 7\Progetti\proloco-iscrizioni"
```

```bash
git remote add origin https://github.com/TUONOME/proloco-iscrizioni.git
```

```bash
git push -u origin main
```

Deve finire con una riga che contiene `main -> main`.

> Nel deposito **non finiscono i dati**: la cartella `dati/` e i file
> `.sqlite` sono esclusi apposta (`.gitignore`). I nomi e i telefoni delle
> persone iscritte non devono mai uscire dal server.

---

## Passo 2 — installare sul server

Dal PC di Windows, per entrare nel server:

```bash
ssh piero@192.168.1.76
```

**2.1 La cartella del codice**

```bash
sudo mkdir -p /srv/app/iscrizioni
```

```bash
sudo git clone https://github.com/TUONOME/proloco-iscrizioni.git /srv/app/iscrizioni/prod
```

**2.2 La cartella dei dati, con i permessi giusti**

Il programma dentro il contenitore gira con l'utente numero **10001**, come
gli altri: la cartella dei dati deve essere sua, altrimenti non può
scriverci.

```bash
sudo mkdir -p /srv/app-dati/iscrizioni/prod /srv/app-dati/iscrizioni/test
```

```bash
sudo chown -R 10001:10001 /srv/app-dati/iscrizioni
```

**2.3 Accendere il programma vero**

```bash
cd /srv/app/iscrizioni/prod && sudo docker compose -f deploy/prod.yml up -d --build
```

La prima volta ci mette un paio di minuti (deve costruire il contenitore).
Alla fine deve comparire `Container iscrizioni-reale  Started`.

**2.4 Controllare che risponda**

```bash
curl -s http://127.0.0.1:8113/salute
```

Deve rispondere esattamente:

```
{"stato":"va bene"}
```

**2.5 La copia di prova** (facoltativa, ma è la vostra abitudine)

```bash
cd /srv/app/iscrizioni/prod && sudo docker compose -f deploy/test.yml up -d --build
```

```bash
curl -s http://127.0.0.1:8213/salute
```

---

## Passo 3 — dare l'indirizzo pubblico

**3.1 Aggiungere il nome al tunnel**

Lo script fa da solo copia di sicurezza, controllo della configurazione e
**ritorno indietro automatico** se qualcosa non torna. È scritto sulla
stessa forma di `~/aggiungi-sossanita-al-tunnel.sh`, che è già in uso qui.

```bash
sudo /srv/app/iscrizioni/prod/servizio/aggiungi-iscrizioni-al-tunnel.sh
```

Deve finire con `FATTO.` e stamparti il comando del passo seguente.

**3.2 Registrare il nome nel DNS** (una volta sola)

```bash
sudo cloudflared tunnel route dns d153afeb-11c8-45b5-9b94-574e36fffa67 iscrizioni.clerm.it
```

> Questo comando **crea un indirizzo pubblico visibile a chiunque**. Da quel
> momento `https://iscrizioni.clerm.it` risponde a tutto il mondo. È quello
> che vogliamo — ma sappi che il passo è questo.

**3.3 Provare da fuori**

Dal **telefono, con i dati e non con il WiFi dell'ufficio**, apri:

```
https://iscrizioni.clerm.it
```

Deve comparire la pagina con il logo della Pro Loco.

---

## Passo 4 — far conoscere il programma al comando «aggiorna»

Così gli aggiornamenti futuri avranno anche per le iscrizioni la copia di
sicurezza e il ritorno indietro automatico.

**4.1 Copia di sicurezza del comando** (si tocca un file che serve a tutti i
programmi: prima si copia)

```bash
sudo cp -p /usr/local/bin/aggiorna /usr/local/bin/aggiorna.prima-di-iscrizioni
```

**4.2 Aprirlo**

```bash
sudo nano /usr/local/bin/aggiorna
```

**4.3** Subito **sopra** la riga che comincia con `*)` (l'ultima del blocco
`case`), aggiungi queste due righe:

```
  iscrizioni/prod) CLONE=/srv/app/iscrizioni/prod; COMPOSE=deploy/prod.yml; CONT=iscrizioni-reale; PORTA=8113; SALUTE=/salute ;;
  iscrizioni/test) CLONE=/srv/app/iscrizioni/test; COMPOSE=deploy/test.yml; CONT=iscrizioni-prova; PORTA=8213; SALUTE=/salute ;;
```

Si salva con **Ctrl+O**, Invio, poi **Ctrl+X**.

**4.4 Controllare che il comando non si sia rotto**

```bash
bash -n /usr/local/bin/aggiorna && echo "il comando e scritto bene"
```

Se **non** compare `il comando e scritto bene`, rimetti subito la copia:

```bash
sudo cp -p /usr/local/bin/aggiorna.prima-di-iscrizioni /usr/local/bin/aggiorna
```

Da qui in avanti, per aggiornare basterà:

```bash
sudo aggiorna iscrizioni prod
```

---

## Passo 5 — le copie di sicurezza dei dati

**Prima controlla se servono**: guarda se le copie di `/srv/app-dati` sono
già fatte da qualcos'altro su questo server. Se lo sono, salta questo passo.

Se non lo sono, nel crontab:

```bash
crontab -e
```

e in fondo:

```
15 2 * * * /srv/app/iscrizioni/prod/servizio/copia_di_sicurezza.sh /srv/app-dati/iscrizioni/prod /srv/archivio/iscrizioni
```

Ogni notte alle 2:15 fa una copia dell'archivio e tiene le ultime 30.

---

## Passo 6 — i controlli finali

1. **La prima password.** Apri `https://iscrizioni.clerm.it/riservato/` e
   scegli la password dell'area riservata. Fallo **subito**, prima che
   l'indirizzo giri: finché non è impostata, la sceglie chiunque arrivi lì.
2. **Le attività vere.** Dall'area riservata correggi le attività del Motor
   Village Fest, che adesso sono inventate.
3. **Una prova vera** dal telefono: iscriviti, poi controlla che l'iscrizione
   compaia nell'area riservata.
4. **Il link scritto nell'area riservata** dev'essere
   `https://iscrizioni.clerm.it/m/...` e non `127.0.0.1`. Se è sbagliato, è
   rimasta spenta `ISCRIZIONI_DIETRO_PROXY` in `deploy/prod.yml`.
5. **Scarica l'elenco per Excel** e controlla gli accenti.

---

## Se qualcosa va storto

Cosa dice il programma:

```bash
sudo docker logs --tail 50 iscrizioni-reale
```

Cosa dice il tunnel:

```bash
sudo journalctl -u cloudflared -n 40
```

Togliere l'indirizzo dal tunnel e tornare com'era prima:

```bash
sudo cp -p /etc/cloudflared/config.yml.prima-di-iscrizioni /etc/cloudflared/config.yml && sudo systemctl restart cloudflared
```

Spegnere il programma senza cancellare niente:

```bash
cd /srv/app/iscrizioni/prod && sudo docker compose -f deploy/prod.yml down
```

I dati restano in `/srv/app-dati/iscrizioni/prod`: spegnere il contenitore
non cancella nessuna iscrizione.
