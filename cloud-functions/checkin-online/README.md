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

- *Deploy*

URL risultante:
`https://checkin-online-113994721180.europe-west1.run.app`

Questo URL è già scritto nella costante `CHECKIN_FN_URL` in `checkin/index.html`.
Se il deploy producesse un URL diverso, aggiornare quella riga. L'hub
(`calendario/index.html`) non chiama la funzione: genera il token da sé.

## 5. Permesso di scrivere su Storage

La funzione gira come `113994721180-compute@developer.gserviceaccount.com`.
Console → **IAM** → quell'account → *Modifica* → *Aggiungi ruolo* →
**Storage Object Admin** (`roles/storage.objectAdmin`) → *Salva*.
(Se hai già fatto questo passo per il backup notturno, è a posto.)

## 6. Prova

1. Nel Calendario apri una prenotazione, premi **Check-in online**, copia il
   link.
2. Aprilo da telefono, compila una scheda con una foto, invia.
3. Verifica: nella scheda "Dettaglio ospiti" compaiono i dati e la miniatura
   della foto; arriva l'email a `MAIL_RECEPTION`.

Se l'email non arriva ma i dati sì: controlla i log della funzione (Console →
la funzione → **Log**) — l'errore SMTP è stampato lì, il resto del check-in
va a buon fine comunque.

---

## Azioni dell'endpoint (POST, corpo JSON)

| `azione` | corpo | risposta |
|---|---|---|
| `carica` | `{ token }` | `{ ok, prenotazione:{…}, testo_privacy, testo_regolamento, esenzioni:[…] }` |
| `invia` | `{ token, ospiti:[…], consensi:{privacy,regolamento}, foto:[{ospite_idx,tipo,data_url}] }` | `{ ok:true }` o `{ ok:false, errore, dettagli? }` |

Il token è 16–64 hex, generato dall'hub, con scadenza (`checkout` + 3 giorni)
registrata in `checkin_links/{token}`.
