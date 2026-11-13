# Area ospite (mini-pannello)

Dà all'ospite un link personale per prenotazione
(`https://gardenhub.it/area-ospite/?t=<token>`) con un mini-pannello a
sezioni. Per ora è operativa solo **Servizio navetta**: l'ospite prenota il
rientro dalla spiaggia scegliendo un orario tra le fasce attive, la richiesta
finisce in `navetta_prenotazioni` e la vedono gli autisti nella dashboard Hub
(`navetta/`, aggiornamento in tempo reale, nessuna notifica push).

Il browser dell'ospite non tocca mai Firestore: parla solo con questa
funzione (Admin SDK). Il collegamento `token → prenotazione` vive nella
collezione `area_ospite_links/{token}`, che le regole negano in lettura a
tutti i client — stesso schema del check-in online.

Progetto Google Cloud: **garden-river-conti-febed** · regione **europe-west1**.
Punto di ingresso: `area_ospite`.

Nessun secret/variabile d'ambiente richiesto: niente SMTP, niente Storage.

---

## 1. Pubblica le regole Firestore

**Firestore → Regole** → aggiungi i blocchi `area_ospite_links` e
`navetta_prenotazioni` (vedi
`firestore-rules/garden-river-conti-febed-CONSOLIDATO.rules`) → *Pubblica*.

## 2. Crea la Cloud Function

Console → **Cloud Run functions** → *Crea funzione*

- Ambiente: **2ª gen.**
- Nome: `area-ospite`
- Regione: `europe-west1`
- Trigger: **HTTPS** · **Consenti chiamate non autenticate**
- Runtime: **Python 3.12**
- **Punto di ingresso**: `area_ospite`
- Editor in linea: incolla `main.py` e `requirements.txt` da questa cartella
- *Deploy*

URL risultante (prevedibile, stesso progetto delle altre funzioni):
`https://area-ospite-113994721180.europe-west1.run.app`

Questo URL va scritto nella costante `AREA_OSPITE_FN_URL` in
`area-ospite/index.html` e in `calendario/index.html`. Se il deploy producesse
un URL diverso, aggiornare quelle due righe.

## 3. Prova completa

1. Nel Calendario apri una prenotazione, premi **Area ospite**, copia il
   link.
2. Aprilo da telefono: compaiono nome/alloggio precompilati; se la
   prenotazione ha già un ombrellone posizionato (pannello "Spiaggia" del
   Calendario), anche quello è precompilato.
3. Scegli un orario e invia: la richiesta compare subito nella dashboard
   `navetta/` con il conto alla rovescia.

---

## Azioni dell'endpoint (POST, corpo JSON)

| `azione` | corpo | risposta |
|---|---|---|
| `carica` | `{ token }` | `{ ok, prenotazione:{nome,telefono,alloggio_nome,checkin,checkout}, spiaggia:{spiaggia_nome,ombrellone}\|null, fasce:[…] }` |
| `navetta_prenota` | `{ token, nome, telefono, alloggio_nome, spiaggia_nome?, orario }` | `{ ok:true, id }` o `{ ok:false, errore }` |
| `manutenzione_segnala` | `{ token, nome, categoria, descrizione, accesso }` | `{ ok:true, id }` o `{ ok:false, errore }` — crea il ticket in `maintenance_tickets` (origine `ospite`, max 5 al giorno per prenotazione) + Telegram + push |

Il token è 16–64 hex. Lo genera l'hub (Calendario → "Area ospite"), stessa
funzione `generaCheckinToken`/scadenza di `checkin_links` (checkout + 3
giorni), nella collezione `area_ospite_links/{token}`.
