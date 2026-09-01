# Regole Firestore — Garden Hub

Regole di sicurezza dei progetti Firebase. **Non vengono deployate da questo
repository**: si incollano a mano nella console Firebase. Questi file servono a
versionarle e a documentare lo stato.

## Contesto: consolidamento in un progetto unico

La suite sta passando **da 3 progetti Firebase a 1**. Target: tutto dentro
`garden-river-conti-febed` (mantiene push, Cloud Function, Storage, service
account). Le collezioni di `garden-river-hub` (`operatori`, `permessi`,
`home_layout`, `meta`) e di `garden-river-magazzino` (`prodotti`, `categorie`)
vengono migrate dentro conti-febed.

Verifica fatta in locale: **`garden-river-conti-febed` NON è in "modalità test"**
— ha già regole che negano le collezioni non previste. `garden-river-hub` e
`garden-river-magazzino` sono da verificare (probabile test mode).

## File

| File | Quando si usa |
|---|---|
| `garden-river-conti-febed-CONSOLIDATO.rules` | **Da deployare su conti-febed durante il cutover** — include le 21 collezioni della suite (le 15 attuali + le 6 migrate). ⚠️ Prima confrontalo con le regole attuali di conti-febed (vedi sotto). |
| `garden-river-conti-febed.rules` | Solo le 15 collezioni attuali. Riferimento / rollback se il consolidamento salta. |
| `storage.rules` | Regole di **Firebase Storage** (Console Firebase → Storage → Regole). Scrittura solo lato server; serve al check-in online per le foto del documento. |
| `garden-river-hub.rules` | Se NON consolidi: blinda il progetto hub. Se consolidi: dopo il cutover, per blindare il vecchio progetto svuotato (o eliminalo). |
| `garden-river-magazzino.rules` | Come sopra per magazzino. |

## Sequenza di cutover (consolidamento)

1. **Copiami le regole attuali di `garden-river-conti-febed`** (console → Firestore
   → Regole). Le fondo io con le 6 collezioni nuove, per non perdere eventuali
   validazioni già presenti. Il file `-CONSOLIDATO.rules` è una bozza da rivedere
   con quelle alla mano.
2. **Deploy** del file consolidato su conti-febed. (Serve *prima* della
   migrazione: lo strumento di migrazione scrive `operatori` ecc. dentro
   conti-febed e senza queste regole verrebbe bloccato.)
3. **Migrazione dati**: apri `scripts/migrazione-firebase.html` servito in locale
   (`http://localhost:8745/scripts/migrazione-firebase.html`), premi **Simula**
   (verifica che nessuna collezione di destinazione risulti già popolata → se sì,
   collisione di nomi, fermati e avvisa), poi **Esegui migrazione**.
4. **Push del codice** (i 3 blocchi Firebase di `index.html` + `magazzino/index.html`
   ora puntano tutti a conti-febed). Da fare **solo dopo** i passi 2 e 3, altrimenti
   la Hub non trova più gli operatori e nessuno riesce a fare login.
5. **Verifica** sul sito live: login, home, Impostazioni, Magazzino, e un giro
   sugli altri moduli.
6. **Blinda i vecchi progetti**: su `garden-river-hub` e `garden-river-magazzino`
   incolla regole che negano tutto (`allow read, write: if false;`), così i dati
   rimasti lì non sono più esposti. Tienili ~1 settimana come rollback, poi
   eliminali dalla console.

## Modello di sicurezza (tutte le versioni)

- Autenticazione client **anonima** → le regole non distinguono admin/operatore
  (resta lato app). Chi non ha fatto login non legge/scrive nulla.
- Si accede **solo** alle collezioni elencate; ogni altro percorso è negato.
- `prenotazioni_eliminate`: copia in sola lettura delle prenotazioni cancellate
  dal Calendario (per lo Storico ospite). Client: `read`/`create`/`update` se
  autenticato, `delete` sempre negato.
- GitHub Actions e Cloud Function usano un **service account** che **bypassa** le
  regole: non serve aprire nulla per loro.

### PIN operatore (dal 09/2026)

I PIN **non sono più in `operatori`**. La verifica avviene sulla Cloud Function
`auth-operatori` (`cloud-functions/auth-operatori/`), che è l'unica a
leggere/scrivere `operatori_pin/{nome}` — hash PBKDF2 salato. Le regole negano
`operatori_pin` a **tutti** i client (`allow read, write: if false`). Il
documento `operatori/{nome}` conserva solo `{ nome, ruolo, haPin }`.

Migrazione una tantum: azione `migra` della funzione (protetta da
`MIGRA_TOKEN`), che trasforma i PIN in chiaro esistenti in hash e poi — con
`pulisci:true` — cancella il campo `pin`.

### Check-in online (dal 09/2026)

Nuova collezione `checkin_links/{token}` = `{ prenId, creato_il, scade_il }`:
l'hub la **crea** quando genera il link check-in di una prenotazione; solo la
Cloud Function `checkin-online` (`cloud-functions/checkin-online/`) risolve
`token → prenotazione`. Le regole permettono ai client solo `create`, mai
`read/update/delete` — un token leggibile darebbe a un client il form di un
ospite altrui.

Va pubblicato anche `storage.rules` (Firebase Storage) per le foto del
documento.

### Limiti noti (autenticazione anonima)

- Dati Alloggiati Web (`ospiti`, `prenotazioni`) → leggibili da chi è
  autenticato. Mitigazione futura: login non anonimo.
- Scrittura libera su `operatori` (ruoli, cancellazioni) da qualsiasi client
  autenticato. Stessa mitigazione.

Restano comunque un miglioramento netto: senza queste regole (modalità test) i
dati sono accessibili **senza alcun login**.

## Se qualcosa si rompe dopo un deploy

Sintomo: una sezione resta su "Caricamento…". Console browser:
`Missing or insufficient permissions`.

- Rimedio: reincolla le regole precedenti e pubblica.
- Poi segnala **quale collezione** dà errore (è nel messaggio) — va aggiunta.
