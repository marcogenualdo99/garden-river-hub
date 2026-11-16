# Shop interno

Market digitale della struttura. **Gestione** nell'Hub (`shop/`, schede Ordini · Prodotti · Categorie · Impostazioni);
**acquisto** nell'Area ospite (sezione «Shop», visibile solo dal giorno di arrivo e solo se lo shop è aperto).

## Dati (Firestore, solo operatori; l'ospite passa dalla Cloud Function)
- `shop_categorie/{id}`: `nome, ordine, attiva`
- `shop_prodotti/{id}`: `titolo, descrizione, prezzo, categoriaId, foto[] (data URL, max 4, ~140KB l'una), attivo, esaurito, giacenza|null, ordine`
- `shop_ordini/{id}`: creato dalla CF. `righe[{id,titolo,prezzo,quantita,importo}], totale, modalita (ritiro|consegna), note, stato (nuovo|pronto|consegnato|annullato), pagamento{metodo:'in_struttura', stato:'da_pagare'|'pagato', importo}`
- `impostazioni/shop`: `attivo, ritiro, consegna, ritiro_luogo, messaggio`

## Azioni CF `area-ospite`
`shop_catalogo`, `shop_prodotto` (tutte le foto), `shop_ordina` (rilegge prezzi e giacenza in transazione), `shop_ordini`. In `carica` c'è anche `shop_attivo`.

## Per attivarlo
1. Pubblicare le regole Firestore (blocchi `shop_*` in `firestore-rules/garden-river-conti-febed-CONSOLIDATO.rules`).
2. Rideployare la CF `area-ospite`.
3. Hub → Shop → creare categorie e prodotti → Impostazioni → «Shop aperto agli ospiti».

## Pagamento PayPal (da fare)
`pagamento` è già strutturato: basterà una azione CF che crea l'ordine PayPal con `totale` e, a cattura avvenuta, imposta `pagamento = {metodo:'paypal', stato:'pagato', id_transazione}`.
