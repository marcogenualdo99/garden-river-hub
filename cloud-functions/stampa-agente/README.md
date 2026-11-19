# Agente di stampa (coda)

Riceve le stampe dai dispositivi senza proxy locale (iPad/iPhone) e le passa
all'app Android **Agente Stampa** installata sul Sunmi V2.

Progetto: **garden-river-conti-febed** · regione **europe-west1** · punto di ingresso `stampa_agente`.

## 1. Regola Firestore
Aggiungi il blocco `coda_stampa` (vedi `firestore-rules/garden-river-conti-febed-CONSOLIDATO.rules`) e *Pubblica*.

## 2. Crea la funzione (Console → Cloud Run functions)
- 2ª gen., nome `stampa-agente`, regione `europe-west1`, trigger HTTPS **consenti chiamate non autenticate**
- Python 3.12, punto di ingresso `stampa_agente`, incolla `main.py` e `requirements.txt`
- **Variabile d'ambiente** `AGENTE_TOKEN` = una stringa casuale lunga (min 16 caratteri, es. 32 hex). Lo stesso valore va scritto nell'app.
- Ruolo IAM: stesso account di servizio delle altre funzioni (accesso a Firestore).

URL atteso: `https://stampa-agente-113994721180.europe-west1.run.app`

## 3. App sul V2
Vedi `android-agente-stampa/LEGGIMI.md`.
