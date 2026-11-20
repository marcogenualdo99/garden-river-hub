# Garden Hub per Sunmi V2 (APK)

App Android senza dipendenze (solo Java + SDK). Resta sempre attiva (servizio in
primo piano, parte da sola all'avvio), chiede alla Cloud Function
`stampa-agente` i lavori in coda e li invia alla stampante in rete (porta 9100).

## Compilare
`./build.sh` -> `build/GardenHub.apk` (usa JDK e SDK in `~/android-toolchain`,
chiave di firma in `~/android-toolchain/agente-stampa.keystore`: conservala,
serve per gli aggiornamenti dell'app).

## Installare sul V2
1. Impostazioni del V2: abilita "Origini sconosciute"/installazione da fonti esterne.
2. Copia `GardenHub.apk` sul V2 (cavo USB / `adb install -r GardenHub.apk`) e aprilo.
3. Apri l'app, incolla il **Token** (uguale a `AGENTE_TOKEN` della funzione), "Salva e avvia".
4. Impostazioni batteria del V2: escludi l'app dal risparmio energetico.

## Uso
- L'app apre la Hub a schermo intero e stampa direttamente sulle stampanti Sunmi (niente proxy).
- Impostazioni: tieni premuto il tasto Indietro.
- L'agente di coda (stampe da iPad/iPhone) parte solo se in Impostazioni e' stato salvato un token: senza token non gira nulla in background.

## Avvisi con app chiusa (v1.2)
- Il servizio `KeepAliveService` chiede ogni ~20 secondi alla funzione `telegram-bot` i nuovi avvisi (evento `feed_notifiche`, collezione `notifiche`) e li mostra come notifiche Android, anche con l'app chiusa o lo schermo spento. Parte da solo all'accensione e si riavvia se l'app viene tolta dalle recenti.
- **Una volta sola**: nella funzione `telegram-bot` impostare la variabile d'ambiente `APP_FEED_KEY` (testo casuale lungo) e ridistribuirla. L'app la riceve da sola alla prima pagina della Hub aperta da un operatore loggato (`feed_chiave`) e non va scritta a mano.
- Reparti: quelli scelti nella Hub (Notifiche) vengono passati al servizio (`GRNativo.impostaReparti`).
- Impostazioni (tieni premuto Indietro): stato degli avvisi, escludi dal risparmio energetico, "Richiedi di nuovo la chiave avvisi".
- Finché il servizio riceve gli avvisi, la pagina non ripete la notifica (`Avvisi.feedAttivo`); senza chiave resta il vecchio ascolto dalla pagina.
- Limite: se l'utente forza l'arresto dell'app dalle impostazioni di Android, nulla gira finché non viene riaperta (senza servizi Google non c'è altro modo).
