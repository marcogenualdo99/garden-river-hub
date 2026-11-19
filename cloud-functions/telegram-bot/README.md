# Bot Telegram — notifiche per reparto

Un bot, sei gruppi: **manutenzione, navetta, pulizie, reception, ristorazione, market**. È l'unico canale di notifica dell'Hub (le notifiche push FCM sono state rimosse).
Progetto Google Cloud: garden-river-conti-febed · regione europe-west1 · entry point `telegram_bot`.

| Evento | Gruppo | Origine |
|---|---|---|
| Nuovo ticket (🚨 se priorità alta) | manutenzione | `manutenzione/index.html` |
| Cambio stato alloggio | pulizie (+ reception se "Pronta") | `alloggi/`, `calendario/` |
| Nuova corsa navetta (ospite o staff) | navetta | CF `area-ospite` |
| Check-in online completato | reception | CF `checkin-online` |
| Nuovo ordine Market (shop interno), con pulsanti Pronto / Consegnato / Segna pagato / Annulla | market | CF `area-ospite` |
| Nuovo ordine ristorazione | ristorazione | CF `area-ospite` (ospite) e controllo `ordini_pendenti` (pagina Ristorazione) |

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

## 4. Crea i gruppi e collegali
Crea un gruppo per reparto, aggiungi il bot e scrivi nel gruppo:
`/collega manutenzione <codice>` (idem `navetta`, `pulizie`, `reception`, `ristorazione`, `market`).
Navetta per autista: `/collega navetta <codice> <Nome autista>` (il nome come in Navetta > Impostazioni). Ogni corsa va al gruppo del suo autista; se non ne ha uno, al gruppo `/collega navetta <codice>` generico.
Altri comandi: `/stato`, `/scollega <codice>`.

## 5. Redeploy delle CF che inviano eventi
`area-ospite` e `checkin-online` (riga `_telegram`). Opzionale: env `TELEGRAM_BOT_URL` se l'URL della funzione non è
`https://telegram-bot-113994721180.europe-west1.run.app`.

Prova: `curl -X POST <URL_FUNZIONE> -H 'Content-Type: application/json' -d '{"evento":"test","richiesto_da":"Prova"}'`

## 6. Eventi programmati (Cloud Scheduler)
Sei eventi partono da Cloud Scheduler, non dall'Hub. Servono la variabile d'ambiente **`CRON_TOKEN`** (stringa casuale) sulla funzione: senza, vengono rifiutati.

| Evento | Gruppo | Cosa fa | Frequenza consigliata |
|---|---|---|---|
| `promemoria_ticket` | manutenzione | Ricorda i ticket ancora aperti: urgenti ogni 2 h, normali ogni 24 h, bassa priorità ogni 72 h (con pulsante "Segna come risolto"). Solo tra le 8 e le 21, max 8 messaggi per giro. Segna `ultimo_promemoria` sul ticket. | ogni ora: `0 * * * *` |
| `ordini_pendenti` | ristorazione | Rete di sicurezza: manda gli ordini con `notified=false` (quelli salvati dalla pagina Ristorazione, che non chiama il bot). Segna `notified` sull'ordine. | ogni 5 minuti: `*/5 * * * *` |
| `risto_sollecito` | ristorazione | Poco prima della chiusura ordini (8:30): elenco delle famiglie che non hanno ancora ordinato pranzo/cena di oggi. Non scrive nulla se hanno ordinato tutti. | ogni giorno alle 7:45: `45 7 * * *` |
| `risto_riepilogo` | ristorazione | Quantità da preparare per il pasto di oggi (per categoria e piatto, note, famiglie senza ordine). Richiede `"pasto":"pranzo"` o `"cena"` nel corpo. | pranzo alle 10:30 `30 10 * * *`, cena alle 17:00 `0 17 * * *` |
| `risto_domani` | ristorazione | Ordini già arrivati per domani (pranzo e cena), con allergie evidenziate e famiglie che non hanno ancora ordinato. | ogni giorno alle 19:00: `0 19 * * *` |
| `riepilogo_mattina` | reception | Arrivi, partenze, alloggi non ancora pronti per chi arriva, ticket urgenti aperti. Una sola volta al giorno (doc `impostazioni/telegram_cron`). | ogni giorno alle 8: `0 8 * * *` |

Scheduler → job HTTP POST, fuso **Europe/Rome**, URL della funzione, header `Content-Type: application/json`, corpo:
`{"evento":"promemoria_ticket","_cron_token":"<CRON_TOKEN>"}` (idem con gli altri, `risto_domani` incluso; per `risto_riepilogo` aggiungi `"pasto":"pranzo"` o `"cena"`, un job ciascuno).

Prova senza inviare nulla: aggiungi `"dry_run":true` al corpo, la risposta contiene l'anteprima. Per rimandare il riepilogo già inviato oggi: `"forza":true`.

## 7. Notifiche nell'app Garden Hub (V2)
Ogni messaggio inviato ai gruppi viene copiato in Firestore `notifiche` (reparti, titolo, testo, ts; solo ultime 24 h). L'app sul V2 le legge e mostra una notifica Android per i reparti scelti in Hub > campana > "Notifiche su questo dispositivo". Serve la regola `notifiche` (lettura staff, scrittura solo Admin SDK) e il redeploy di `telegram-bot`.
