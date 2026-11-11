# navetta-pulizia

Cancella le corse navetta `completata` / `annullata` piu' vecchie di N giorni
(default 3; si cambia da Navetta > Impostazioni).

Deploy (Console Google Cloud, come le altre funzioni):
- Cloud Run functions > Crea funzione, runtime Python 3.12, entry point `navetta_pulizia`, trigger HTTPS
- Variabile d'ambiente: `PULIZIA_TOKEN` = una stringa segreta a caso
- Cloud Scheduler: job giornaliero (es. `0 4 * * *`, Europe/Rome), metodo GET, URL funzione + `?token=<PULIZIA_TOKEN>`
- Il service account della funzione deve avere il ruolo Cloud Datastore User (come le altre)
