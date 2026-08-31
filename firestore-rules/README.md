# Regole Firestore — Garden Hub

Le regole di sicurezza dei 3 progetti Firebase della suite. **Non vengono
deployate da questo repository**: vanno incollate a mano nella console Firebase
di ogni progetto. Questi file servono a tenerne traccia e a versionarle.

| File | Progetto Firebase | Console |
|---|---|---|
| `garden-river-hub.rules` | `garden-river-hub` | operatori, permessi, layout home |
| `garden-river-conti-febed.rules` | `garden-river-conti-febed` | dati operativi condivisi + token push |
| `garden-river-magazzino.rules` | `garden-river-magazzino` | magazzino bar |

## Cosa fanno

Portano i database dalla **"modalità test"** (lettura e scrittura aperte a
*chiunque* su internet, spesso con scadenza a 30 giorni) a: **serve almeno un
login**, e si può toccare **solo le collezioni che l'app usa davvero**.

Cosa **non** cambia:
- L'app continua a funzionare identica: usa già `signInAnonymously`, quindi i
  client sono "autenticati" agli occhi delle regole.
- Gli script GitHub Actions e le Cloud Function usano un *service account*
  (Admin SDK) che **bypassa le regole**: non serve fare nulla per loro.

Cosa **non** risolvono (limiti dell'autenticazione anonima, vedi commenti nei
file):
- I PIN operatore in chiaro restano leggibili da chi è autenticato → resta da
  fare lo step "hashing PIN + verifica su Cloud Function".
- I dati Alloggiati Web (`ospiti`, `prenotazioni`) restano leggibili da chi è
  autenticato → mitigabile in futuro con login non anonimo.

Restano comunque un **miglioramento netto**: oggi, in modalità test, quei dati
sono accessibili anche **senza alcun login**.

## Come deployare (per ogni progetto, uno alla volta)

1. [console.firebase.google.com](https://console.firebase.google.com) → seleziona il progetto
2. Menu a sinistra: **Firestore Database** → scheda **Regole** (Rules)
3. **Prima copia da qualche parte le regole attuali** (incollale in un file di
   testo), così puoi tornare indietro se qualcosa si rompe
4. Cancella tutto e incolla il contenuto del file `.rules` corrispondente
5. **Pubblica** (Publish)
6. Subito dopo, apri l'app e verifica il modulo che usa quel progetto (vedi
   sotto). Se qualcosa non carica → torna alle regole vecchie e segnalamelo.

### Ordine consigliato e verifica

| # | Progetto | Dopo il publish, verifica che… |
|---|---|---|
| 1 | `garden-river-magazzino` | Magazzino: le giacenze si caricano, aggiungi/modifica un prodotto |
| 2 | `garden-river-hub` | Login operatore funziona, la home carica, (da admin) Impostazioni → operatori e permessi |
| 3 | `garden-river-conti-febed` | Calendario carica le prenotazioni; Conti carica gli ospiti; Pulizie cambia stato a un alloggio; Ristorazione carica ordini; Manutenzione carica ticket; Spiaggia carica le prenotazioni |

Fai un progetto alla volta e verifica prima di passare al successivo: se si
rompe qualcosa sai subito quale set di regole è il colpevole.

## Se qualcosa si rompe

Sintomo tipico: una sezione dell'app resta su "Caricamento…" o mostra errore di
connessione. In console del browser vedrai `Missing or insufficient permissions`.

- Rimedio immediato: reincolla le regole vecchie e pubblica.
- Poi segnalami **quale collezione** dà errore (è nel messaggio della console):
  vuol dire che l'app usa una collezione che non ho elencato e va aggiunta.
