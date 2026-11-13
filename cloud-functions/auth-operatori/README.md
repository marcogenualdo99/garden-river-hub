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
