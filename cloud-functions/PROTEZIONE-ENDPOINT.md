# Protezione endpoint notifiche (novembre 2026)

Prima chiunque conoscesse l'URL poteva mandare messaggi Telegram e push allo staff.
Ora serve **o** l'ID token di un operatore (la Hub lo manda da sola) **o** il segreto
condiviso `INTERNAL_TOKEN` (header `X-Internal-Token`, per le chiamate tra funzioni).

| Funzione | Cosa richiede autorizzazione | Variabile da impostare |
|---|---|---|
| `telegram-bot` | tutti gli eventi (webhook Telegram e cron restano come prima) | `INTERNAL_TOKEN` |
| `notifiche-manutenzione` | `ticket`, `test` (`controlla_pendenti` resta aperto: lo Scheduler non manda token) | `INTERNAL_TOKEN` |
| `notifiche-pulizie` | tutto | — (solo staff dal browser) |
| `notifiche-ristorazione` | solo `test` (`ordine` resta aperto: lo manda la pagina ospite) | — |
| `area-ospite` | chiama telegram-bot / notifiche-manutenzione | `INTERNAL_TOKEN` (stesso valore) |
| `checkin-online` | chiama telegram-bot; azione `cron` ora **fail-closed** | `INTERNAL_TOKEN` (stesso valore) e `CRON_TOKEN` deve esistere |

## Ordine (importante)
1. Genera un valore: `openssl rand -hex 24` e usa lo STESSO su tutte e 4 le funzioni.
2. Rideploya le 7 funzioni modificate (vedi tabella + `backup-firestore`).
3. Solo dopo, push del codice client (altrimenti il browser manda `Authorization` a funzioni
   che non lo ammettono nel CORS e le notifiche falliscono).
4. Verifica: cambio stato alloggio (notifica Telegram/push), ticket manutenzione, un
   check-in di prova, e il job giornaliero del check-in (Scheduler deve mandare `_cron_token`).
