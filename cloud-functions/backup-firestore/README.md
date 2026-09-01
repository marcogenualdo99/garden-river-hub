# Backup automatico del database (Firestore → Google Cloud Storage)

Fa una copia di tutto il database (tutte le collezioni e sottocollezioni) ogni
notte, in un bucket di archiviazione tuo. È l'export ufficiale di Firestore, si
ripristina con un comando.

Progetto Google Cloud: **garden-river-conti-febed** · regione **europe-west1**.

Fai i passi in ordine; ognuno è indipendente, se qualcosa non torna fermati.

---

## 1. Crea il bucket dove finiranno i backup

Console Google Cloud → **Cloud Storage** → **Bucket** → *Crea*

- Nome: `garden-river-backup` (deve essere unico a livello mondiale; se occupato
  usa `garden-river-backup-2026` o simile e ricordati il nome esatto)
- Tipo di località: **Region** → `europe-west1` (stessa del database)
- Classe di archiviazione: **Standard**
- Controllo dell'accesso: **Uniforme**
- Protezione: lascia i default → *Crea*

## 2. Regola di conservazione (cancella i backup vecchi da soli)

Nel bucket appena creato → scheda **Ciclo di vita** → *Aggiungi una regola*

- Azione: **Elimina oggetto**
- Condizione: **Età** = `30` giorni → *Crea*

(Tieni 30 giorni di backup; alza il numero se vuoi tenerne di più.)

## 3. Dai i permessi all'account di servizio

Le Cloud Function girano come
`113994721180-compute@developer.gserviceaccount.com`.

**a) Permesso di fare export** — Console → **IAM e amministrazione** → **IAM** →
trova quell'account → *Modifica* (matita) → *Aggiungi un altro ruolo* →
**Amministratore importazione/esportazione Cloud Datastore**
(`roles/datastore.importExportAdmin`) → *Salva*

**b) Permesso di scrivere nel bucket** — Cloud Storage → bucket
`garden-river-backup` → scheda **Autorizzazioni** → *Concedi accesso* →
- Nuove entità: `113994721180-compute@developer.gserviceaccount.com`
- Ruolo: **Storage Object Admin** (`roles/storage.objectAdmin`)
- *Salva*

## 4. Scegli un token segreto

Serve perché nessuno possa far partire backup a caso conoscendo l'URL.
Inventane uno lungo a caso, es. da https://passwordsgenerator.net (40+ caratteri).
Chiamalo **BACKUP_TOKEN**, tienilo da parte per i passi 5 e 6.

## 5. Crea la Cloud Function

Console → **Cloud Run functions** → *Crea funzione*

- Ambiente: **2ª gen.**
- Nome funzione: `backup-firestore`
- Regione: `europe-west1`
- Trigger: **HTTPS** · **Consenti chiamate non autenticate**
- *Avanti*
- Runtime: **Python 3.12**
- **Punto di ingresso**: `backup_firestore`
- Editor in linea: incolla `main.py` e `requirements.txt` da questa cartella
- **Variabili e secret** → *Variabili d'ambiente di runtime* → aggiungi:
  | Nome | Valore |
  |---|---|
  | `BACKUP_TOKEN` | il token del passo 4 |
  | `BACKUP_BUCKET` | `gs://garden-river-backup` (o il nome che hai usato) |
- *Deploy*

URL risultante: `https://backup-firestore-113994721180.europe-west1.run.app`

**Prova subito**: apri nel browser
`https://backup-firestore-113994721180.europe-west1.run.app?token=IL_TUO_TOKEN`
→ deve rispondere `{"ok": true, "destinazione": "gs://garden-river-backup/2026-..."}`.
Dopo 1-2 minuti nel bucket compare una cartella con la data. Se dà `errore` o
`500`, ricontrolla i permessi del passo 3.

## 6. Programma il backup notturno

Console → **Cloud Scheduler** → *Crea job*

- Nome: `backup-firestore-notte`
- Regione: `europe-west1`
- Frequenza: `0 3 * * *`  (ogni notte alle 3:00)
- Fuso orario: **Central European Time (Italy)**
- Tipo di destinazione: **HTTP**
- URL: `https://backup-firestore-113994721180.europe-west1.run.app`
- Metodo HTTP: **POST**
- *Mostra altro* → **Intestazioni HTTP** → aggiungi:
  `X-Backup-Token` = il token del passo 4
- *Crea*

Poi selezionalo → *Forza esecuzione* per verificare che funzioni anche da qui.

---

## Ripristino (in caso di disastro)

Non serve `gcloud` sul Mac: si fa da **Cloud Shell** (icona `>_` in alto a destra
nella Console).

```bash
gcloud config set project garden-river-conti-febed
# elenca i backup disponibili
gcloud storage ls gs://garden-river-backup/
# ripristina da una data specifica
gcloud firestore import gs://garden-river-backup/2026-09-01_030000
```

**Attenzione:** l'import *sovrascrive* i documenti con lo stesso id e lascia
intatti gli altri — non è un "torna esattamente a quella notte". Per un
ripristino pulito conviene importare in un **database nuovo** (crearlo prima con
`gcloud firestore databases create --database=ripristino --location=europe-west1`)
e controllare lì prima di spostare l'app.

## Costo

Trascurabile per un database di questa dimensione: l'export costa come una
lettura per documento (qualche centesimo) più lo spazio su Storage
(~0,02 €/GB al mese). Con 30 giorni di retention si parla di pochi euro l'anno.
