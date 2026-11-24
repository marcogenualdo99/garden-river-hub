# auth-operatori — sessione operatore (novembre 2026)

Dopo la verifica del PIN la funzione risponde con un `token` (custom token
Firebase, claim `operatore`, `ruolo`, `nome`). Le regole Firestore/Storage
richiedono quel claim. Nuova azione `rinnova` per le app Firebase con nome.

## Prima del deploy (una tantum)
1. Console Google Cloud → IAM → trova il service account con cui gira la
   funzione (di solito `113994721180-compute@developer.gserviceaccount.com`).
2. Aggiungi il ruolo **Service Account Token Creator** (`roles/iam.serviceAccountTokenCreator`)
   su **se stesso** (IAM → Service Accounts → quell'account → Autorizzazioni → Concedi accesso).
3. Verifica che l'API **IAM Service Account Credentials** sia abilitata.

## Ordine di rilascio (importante)
1. Rideploy `auth-operatori` e `area-ospite` (codice sorgente di questa cartella).
2. Push del codice client → l'accesso con PIN funziona ancora con le vecchie regole.
3. Prova il login reale su gardenhub.it.
4. Solo dopo: pubblica `garden-river-conti-febed-CONSOLIDATO.rules` e `storage.rules`.

## Blocco progressivo e limite per IP (24/11/2026)

- **PIN**: il server ora impone almeno 6 cifre (`PIN_MIN_LEN`) per i NUOVI PIN, come già faceva il client.
  I PIN esistenti continuano a funzionare.
- **Blocco progressivo**: dopo 5 errori consecutivi su un operatore, attesa di 15 min; la serie successiva
  60 min, poi 4 ore, poi 24 ore (tetto). Si azzera con un accesso riuscito, o dopo 24 ore dalla FINE
  dell'ultimo blocco senza errori. Il conteggio è in transazione (richieste parallele non lo aggirano).
- **Limite per IP**: dopo `IP_MAX_FALLITI` PIN sbagliati in `IP_FINESTRA_S` dallo stesso indirizzo la funzione
  risponde `429 troppi_tentativi` SENZA contare contro l'operatore, così chi sbaglia da fuori non può bloccare
  un collega. L'IP è l'ULTIMO elemento di `X-Forwarded-For`: dopo il deploy controlla nei log che sia l'IP
  del cliente e non quello del bilanciatore.
- Un admin sblocca un collega con "Reset PIN" (il collega reimposta il PIN al login successivo).

Ordine: rideploy della funzione, poi push del client (`index.html` mostra l'attesa in ore e gestisce `troppi_tentativi`).

### Ripristino da parte di un admin (sempre possibile)
- **Sblocca** (nuovo, azione `sblocca`): un admin con la sessione aperta toglie il blocco a un operatore SENZA
  cambiargli il PIN. Vale anche per se stesso. Il ruolo si rilegge dal DB, non dal token.
- **Reset PIN** (azione `reset`): azzera il PIN (e quindi anche il blocco); l'operatore ne imposta uno nuovo
  al prossimo accesso. Richiede il PIN dell'admin.
- **Emergenza** (tutti gli admin bloccati e nessuna sessione aperta): Console Firebase → Firestore →
  `operatori_pin/{nome}` → imposta `tentativi`, `blocchi`, `bloccato_fino` a 0 (oppure elimina il documento per
  azzerare il PIN). Il limite per IP si libera da solo entro 10 minuti.

## Codice di attivazione (24/11/2026)

Prima `imposta` (primo PIN) non chiedeva nulla: chiunque conoscesse il nome di un operatore senza PIN
(nuovo, o appena resettato) poteva scegliere il PIN al posto suo. Ora serve un **codice di attivazione**.

- L'admin lo genera dalla Hub: **Impostazioni → Operatori → Genera codice** (operatore senza PIN) oppure
  riceve il codice subito dopo **Reset PIN**. È di 6 cifre, monouso, vale 24 ore (`ATTIVAZIONE_ORE`) e si
  mostra una volta sola. Nel DB (`operatori_attivazione/{nome}`, negata ai client perché senza regola) c'è l'hash.
- Al primo accesso l'operatore digita: codice → nuovo PIN → ripete il PIN.
- Dopo 5 codici sbagliati il codice si invalida (l'admin ne genera un altro); gli errori contano anche per il
  limite per IP.
- Nuove azioni: `codice_attivazione` (solo admin con sessione), `stato_attivazione` (dice al login se il codice
  serve). `reset` ora risponde anche con `codice` e `scade`.
- **Prima installazione / recupero**: se NESSUN admin ha un PIN, un admin può scegliere il proprio PIN senza
  codice (`_bootstrap_aperto`); si chiude appena un admin ha un PIN. Vale solo per operatori con ruolo admin.
- Operatori che oggi non hanno un PIN: al prossimo accesso servirà un codice generato da un admin.
- Compatibilità: il vecchio client non manda il codice, quindi chi non ha PIN non riesce più a impostarlo finché
  non si pubblica il client nuovo. Ordine: rideploy della funzione, poi push di `index.html`.
