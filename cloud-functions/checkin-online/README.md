# Check-in online ospiti

Dà all'ospite un link personale (`https://gardenhub.it/checkin/?t=<token>`) da
compilare prima dell'arrivo: anagrafica di tutti gli occupanti, dati e **foto
del documento**, consenso privacy/regolamento. Quando l'ospite invia, i dati
finiscono nella scheda "Dettaglio ospiti" della prenotazione e la reception
riceve una **email** di notifica.

Il browser dell'ospite non tocca mai Firestore/Storage: parla solo con questa
funzione (Admin SDK). Il collegamento `token → prenotazione` vive nella
collezione `checkin_links/{token}`, che le regole negano in lettura a tutti i
client.

Progetto Google Cloud: **garden-river-conti-febed** · regione **europe-west1**.
Punto di ingresso: `checkin_online`.

---

## 1. Attiva Firebase Storage (una volta sola)

Console Firebase → **Storage** → *Inizia* → località `europe-west1` (o
`eur3`) → parti in **modalità produzione**. Sblocca anche il modulo "Documenti"
del Calendario.

Poi pubblica le regole Storage: **Storage → Regole** → incolla il contenuto di
`firestore-rules/storage.rules` → *Pubblica*.

## 2. Pubblica la regola Firestore

**Firestore → Regole** → aggiungi il blocco `checkin_links` (vedi
`firestore-rules/garden-river-conti-febed-CONSOLIDATO.rules`) → *Pubblica*.

## 3. Casella email Aruba

Serve una casella del dominio (es. `reception@gardenhub.it`) con la sua
password. Nessuna configurazione lato Aruba oltre ad avere la casella attiva;
Aruba usa `smtps.aruba.it:465` (SSL).

## 4. Crea la Cloud Function

Console → **Cloud Run functions** → *Crea funzione*

- Ambiente: **2ª gen.**
- Nome: `checkin-online`
- Regione: `europe-west1`
- Trigger: **HTTPS** · **Consenti chiamate non autenticate**
- Runtime: **Python 3.12**
- **Punto di ingresso**: `checkin_online`
- Editor in linea: incolla `main.py` e `requirements.txt` da questa cartella
- **Variabili e secret** → *Variabili d'ambiente di runtime*:

  | Nome | Valore | Note |
  |---|---|---|
  | `SMTP_USER` | `reception@gardenhub.it` | casella Aruba |
  | `SMTP_PASS` | password della casella | meglio come **secret** |
  | `MAIL_FROM` | `reception@gardenhub.it` | mittente (default = `SMTP_USER`) |
  | `MAIL_RECEPTION` | indirizzo che riceve le notifiche | può essere lo stesso |
  | `SMTP_HOST` | `smtps.aruba.it` | opzionale, è il default |
  | `SMTP_PORT` | `465` | opzionale, è il default |
  | `STORAGE_BUCKET` | `garden-river-conti-febed.firebasestorage.app` | opzionale, è il default |
  | `INVITO_GIORNI_PRIMA` | `5` | quanti giorni prima dell'arrivo parte l'email di invito (default 5) |
  | `CRON_TOKEN` | una stringa lunga a caso | protegge il job giornaliero; se assente, `cron` è aperto |

- *Deploy*

URL risultante:
`https://checkin-online-113994721180.europe-west1.run.app`

Questo URL è già scritto nella costante `CHECKIN_FN_URL` in `checkin/index.html`
e in `calendario/index.html`. Se il deploy producesse un URL diverso, aggiornare
quelle due righe.

## 5. Permesso di scrivere su Storage

La funzione gira come `113994721180-compute@developer.gserviceaccount.com`.
Console → **IAM** → quell'account → *Modifica* → *Aggiungi ruolo* →
**Storage Object Admin** (`roles/storage.objectAdmin`) → *Salva*.
(Se hai già fatto questo passo per il backup notturno, è a posto.)

## 6a. Prova solo l'email (senza fare un check-in)

Da terminale, o incollando l'URL con `curl`:

```
curl -X POST https://checkin-online-113994721180.europe-west1.run.app \
  -H "Content-Type: application/json" -d '{"azione":"test_email"}'
```

- `{"ok": true, "inviata_a": "..."}` → arriva un'email "Test check-in online" a
  `MAIL_RECEPTION`. Credenziali Aruba a posto.
- `{"ok": false, "errore": "invio fallito: ..."}` → l'errore SMTP è nel
  messaggio (di solito password errata, o la casella Aruba non ha l'invio SMTP
  abilitato).

## 6. Prova completa

1. Nel Calendario apri una prenotazione, premi **Check-in online**, copia il
   link.
2. Aprilo da telefono, compila una scheda con una foto, invia.
3. Verifica: nella scheda "Dettaglio ospiti" compaiono i dati e la miniatura
   della foto; arriva l'email a `MAIL_RECEPTION`.

Se l'email non arriva ma i dati sì: controlla i log della funzione (Console →
la funzione → **Log**) — l'errore SMTP è stampato lì, il resto del check-in
va a buon fine comunque.

## 7. Invio automatico dell'invito (Cloud Scheduler)

L'email di invito al cliente parte da sola qualche giorno prima dell'arrivo. Il
job giornaliero si crea come quello del backup notturno.

**Prima, prova a vuoto** (non manda niente, elenca solo):

```
curl -X POST https://checkin-online-113994721180.europe-west1.run.app \
  -H "Content-Type: application/json" \
  -d '{"azione":"cron","dry_run":true,"_cron_token":"IL_TUO_CRON_TOKEN"}'
```

Risposta tipo `{"ok":true,"giorni":5,"inviati":0,"saltati":N,"anteprima":[…]}`:
in `anteprima` vedi le prenotazioni a cui *manderebbe* l'invito. Se il conto
torna, crea il job.

**Cloud Scheduler** → *Crea job*
- Nome: `checkin-invito-giornaliero`
- Regione: `europe-west1`
- Frequenza: `0 10 * * *`  (ogni giorno alle 10:00)
- Fuso orario: **Central European Time (Italy)**
- Tipo destinazione: **HTTP**
- URL: `https://checkin-online-113994721180.europe-west1.run.app`
- Metodo: **POST**
- Corpo del messaggio: `{"azione":"cron"}`
- *Mostra altro* → **Intestazioni HTTP** → `X-Cron-Token` = lo stesso valore di `CRON_TOKEN`
- *Crea* → poi *Forza esecuzione* per una prova reale

Cambia `INVITO_GIORNI_PRIMA` (variabile della funzione) per anticipare/posticipare.
Ogni prenotazione riceve l'invito **una volta sola** (campo `checkin_invito` sul
documento). Salta quelle senza email, con check-in già fatto o già compilate.

---

## Azioni dell'endpoint (POST, corpo JSON)

| `azione` | corpo | risposta |
|---|---|---|
| `carica` | `{ token }` | `{ ok, prenotazione:{…}, testo_privacy, testo_regolamento, esenzioni:[…] }` |
| `invia` | `{ token, ospiti:[…], consensi:{…}, foto:[…] }` | `{ ok:true }` o `{ ok:false, errore, dettagli? }` |
| `invito` | `{ prenId, forza? }` | manda l'invito a `p.email` — usato dal pulsante nell'hub |
| `cron` | `{ _cron_token, dry_run? }` | job giornaliero, invito a chi arriva entro N giorni |
| `test_email` | `{}` | email di prova a `MAIL_RECEPTION` |

Il token è 16–64 hex, con scadenza (`checkout` + 3 giorni) in `checkin_links/{token}`.
Lo genera l'hub quando apri il pannello, o la funzione quando manda l'invito.
