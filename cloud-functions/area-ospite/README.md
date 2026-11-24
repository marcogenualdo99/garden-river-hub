# Area ospite (mini-pannello)

Dà all'ospite un link personale per prenotazione
(`https://gardenhub.it/area-ospite/?t=<token>`) con un mini-pannello a
sezioni. Per ora è operativa solo **Servizio navetta**: l'ospite prenota il
rientro dalla spiaggia scegliendo un orario tra le fasce attive, la richiesta
finisce in `navetta_prenotazioni` e la vedono gli autisti nella dashboard Hub
(`navetta/`, aggiornamento in tempo reale, nessuna notifica push; gli avvisi vanno su Telegram).

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
| `shop_catalogo` / `shop_prodotto` / `shop_ordina` / `shop_ordini` / `shop_foto_consegna` | v. `shop/README.md` | catalogo, foto, creazione ordine (prezzi e giacenza riletti in transazione), stato ordini dell'ospite |

## Pagamento con carta (PayPal, pagamenti avanzati)

Variabili d'ambiente della CF (mai nel codice): `PAYPAL_CLIENT_ID`, `PAYPAL_SECRET`, `PAYPAL_ENV` (`sandbox` oppure `live`, default sandbox).
Azioni: `shop_paypal_crea` (crea l'ordine PayPal con l'importo riletto dal database) e `shop_paypal_cattura` (cattura, verifica importo e stato COMPLETED, segna l'ordine `pagamento.stato = pagato` e avvisa il gruppo Market).
Senza le variabili resta attivo il fallback con link PayPal.Me (se compilato in Hub → Shop → Impostazioni). La carta e' offerta solo con consegna in alloggio, come ultima opzione.

### Pagamento prima dell'ordine (carta)
- Con la carta l'ordine nasce `in_attesa_pagamento` (nascosto a Hub e ospite, giacenza scalata). Solo `shop_paypal_cattura` riuscita lo porta a `nuovo`, lo segna `pagato` e manda UN messaggio Telegram (con metodo e stato). Se l'ospite annulla (`shop_annulla_attesa`) o dopo 30 minuti la giacenza torna disponibile (`abbandonato` / `scaduto`).
- PayPal: intent AUTHORIZE → controllo circuito (solo Visa, Mastercard, Maestro, `SHOP_CARTE_OK`) e importo → capture; altrimenti void dell'autorizzazione.
- Importo minimo carta: `impostazioni/shop.carta_min` (default 5 euro), controllato anche lato server.

### Prenotazione tavolo (Ristorazione)
- Azioni: `ristorazione_prenota_info` (giorni prenotabili, servizi e turni attivi, persone del gruppo, prenotazioni dell'ospite), `ristorazione_prenota`, `ristorazione_prenota_annulla`.
- Dove si scrive: ospite in pensione → `famiglie_ristorazione/{id}.prenotazioni.{idPren}`; ospite senza pasti inclusi → `impostazioni/ristorazione_pren_libere.pren.{idPren}` (con `calendario_id`). Campi: `data, pasto, turno, persone, tavolo, note, origine:'ospite', aggiornata`.
- Orari/turni/giorni: `impostazioni/ristorazione_turni` (li imposta lo staff in Ristorazione > Impostazioni; default pranzo 12:30/13:30, cena 19:30/21:00, 15 giorni).
- Regole server: giorno tra oggi (o arrivo) e partenza entro `giorni`; turno valido e non a meno di 30 minuti; persone 1..ospiti del gruppo (sommando le prenotazioni dello stesso servizio); niente doppioni sullo stesso turno; massimo 12 prenotazioni future per ospite; si annullano solo le proprie e solo fino a `annulla_min` minuti prima del turno (impostazione `impostazioni/ristorazione_turni.annulla_min`, default 30; senza orario fino al giorno prima).
- Ogni prenotazione/annullamento avvisa Telegram (gruppo Ristorazione) con l'evento `prenotazione` del bot; la CF `telegram-bot` copia l'avviso in `notifiche` per l'app.
- Ridistribuire anche `telegram-bot` (nuovo evento) oltre ad `area-ospite`.

## Meteo

Azione `meteo`: la card meteo della home non chiama piu' servizi esterni dal browser. La funzione legge `meteo_cache/garden` (collezione negata ai client, scritta solo da qui) e la rinnova al massimo ogni 30 minuti: fonte principale MET Norway, riserva Open-Meteo, e se falliscono entrambe l'ultimo dato salvato (max 6 ore). Nessuna nuova regola Firestore e nessuna variabile d'ambiente. Se la funzione non risponde, la pagina ripiega su Open-Meteo diretto.

## Accesso col codice famiglia (vecchia pagina `ristorazione/?f=CODICE`) — 24/11/2026

I link/QR già consegnati agli ospiti portano il **codice famiglia**, non il token dell'Area ospite.
La pagina `ristorazione/index.html` non parla più con Firestore: usa queste azioni (stessa funzione,
nessun costo fisso in più), così le collezioni `famiglie_ristorazione`, `ordini_ristorazione` e
`menu_ristorazione` sono chiuse agli anonimi (solo `staff()`).

| Azione | Cosa fa |
|---|---|
| `risto_codice_carica` | famiglia + menu dei due giorni + ordini esistenti (solo i campi necessari) |
| `risto_codice_stato` | solo lo sblocco orario (una lettura); la pagina lo chiama quando l'ospite torna sulla scheda |
| `risto_codice_ordina` | stessa logica di `ristorazione_ordina` (quote, mezza pensione, orario limite, Telegram) |
| `risto_codice_annulla` | toglie un ordine non ancora servito, solo entro l'orario limite |

- Il codice scade il giorno dopo il check-out (`COD_SCADENZA_GIORNI`).
- Tentativi sbagliati limitati per IP (`COD_MAX_FALLITI` ogni `COD_FINESTRA_S`), in memoria per istanza.
  L'IP è l'ULTIMO elemento di `X-Forwarded-For`: dopo il deploy controlla nei log che sia davvero l'IP
  del cliente e non quello del bilanciatore (altrimenti tutti condividerebbero lo stesso contatore).
- Allineamento col Calendario come per il link: date, trattamento e n. ospiti vengono dalla prenotazione.

### Ordine di pubblicazione (importante)
1. **Rideploy** della funzione `area-ospite` (Console Google Cloud).
2. **Push** di `ristorazione/index.html` (usa le nuove azioni).
3. Provare un link vero (`ristorazione/?f=CODICE`): menu visibile, ordine, annullo.
4. Solo ora **pubblicare le regole** (`firestore-rules/garden-river-conti-febed-CONSOLIDATO.rules`).
   Dopo questo passo le vecchie pagine rimaste aperte nei browser non funzionano più.
