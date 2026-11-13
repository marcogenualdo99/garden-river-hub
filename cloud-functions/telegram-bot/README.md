# Bot Telegram — notifiche per reparto

Un bot, quattro gruppi: **manutenzione, navetta, pulizie, reception**.
Progetto Google Cloud: garden-river-conti-febed · regione europe-west1 · entry point `telegram_bot`.

| Evento | Gruppo | Origine |
|---|---|---|
| Nuovo ticket (🚨 se priorità alta) | manutenzione | `manutenzione/index.html` |
| Cambio stato alloggio | pulizie (+ reception se "Pronta") | `alloggi/`, `calendario/` |
| Nuova corsa navetta (ospite o staff) | navetta | CF `area-ospite` |
| Check-in online completato | reception | CF `checkin-online` |

## 1. Crea il bot
Telegram → **@BotFather** → `/newbot` → copia il **token**.
Poi `/setprivacy` → *Disable* (così il bot vede i comandi nei gruppi).

## 2. Deploy (Console Google Cloud → Cloud Run → Crea funzione)
Nome `telegram-bot`, Python 3.12, accesso pubblico (non autenticato), sorgenti = questa cartella.
Variabili d'ambiente:
- `TELEGRAM_BOT_TOKEN` — token di BotFather
- `TELEGRAM_WEBHOOK_SECRET` — stringa casuale (solo lettere/numeri/_/-)
- `TELEGRAM_SETUP_CODE` — codice che lo staff scrive per collegare un gruppo

## 3. Collega il webhook (una volta)
Apri nel browser (sostituisci i valori):
`https://api.telegram.org/bot<TOKEN>/setWebhook?url=<URL_FUNZIONE>&secret_token=<WEBHOOK_SECRET>`

## 4. Crea i 4 gruppi e collegali
Crea un gruppo per reparto, aggiungi il bot e scrivi nel gruppo:
`/collega manutenzione <codice>` (idem `navetta`, `pulizie`, `reception`).
Navetta per autista: `/collega navetta <codice> <Nome autista>` (il nome come in Navetta > Impostazioni). Ogni corsa va al gruppo del suo autista; se non ne ha uno, al gruppo `/collega navetta <codice>` generico.
Altri comandi: `/stato`, `/scollega <codice>`.

## 5. Redeploy delle CF che inviano eventi
`area-ospite` e `checkin-online` (riga `_telegram`). Opzionale: env `TELEGRAM_BOT_URL` se l'URL della funzione non è
`https://telegram-bot-113994721180.europe-west1.run.app`.

Prova: `curl -X POST <URL_FUNZIONE> -H 'Content-Type: application/json' -d '{"evento":"test","richiesto_da":"Prova"}'`

## 6. Eventi programmati (Cloud Scheduler)
Due eventi partono da Cloud Scheduler, non dall'Hub. Servono la variabile d'ambiente **`CRON_TOKEN`** (stringa casuale) sulla funzione: senza, vengono rifiutati.

| Evento | Gruppo | Cosa fa | Frequenza consigliata |
|---|---|---|---|
| `promemoria_ticket` | manutenzione | Ricorda i ticket ancora aperti: urgenti ogni 2 h, normali ogni 24 h, bassa priorità ogni 72 h (con pulsante "Segna come risolto"). Solo tra le 8 e le 21, max 8 messaggi per giro. Segna `ultimo_promemoria` sul ticket. | ogni ora: `0 * * * *` |
| `riepilogo_mattina` | reception | Arrivi, partenze, alloggi non ancora pronti per chi arriva, ticket urgenti aperti. Una sola volta al giorno (doc `impostazioni/telegram_cron`). | ogni giorno alle 8: `0 8 * * *` |

Scheduler → job HTTP POST, fuso **Europe/Rome**, URL della funzione, header `Content-Type: application/json`, corpo:
`{"evento":"promemoria_ticket","_cron_token":"<CRON_TOKEN>"}` (idem con `riepilogo_mattina`).

Prova senza inviare nulla: aggiungi `"dry_run":true` al corpo, la risposta contiene l'anteprima. Per rimandare il riepilogo già inviato oggi: `"forza":true`.
