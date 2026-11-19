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
