# Fiscalizzazione da tutti i dispositivi dell'ufficio

Per far sì che **qualsiasi dispositivo** (PC, Mac, tablet, telefono) possa
emettere scontrini fiscali — a patto che l'operatore abbia il permesso — si
usa **un solo proxy condiviso** su una macchina sempre accesa.

```
  Tablet / PC / telefono  ──HTTPS + token──▶  PC "server" (proxy)  ──TCP──▶  Registratore ItalRetail
```

## 1. Scegli la macchina "server"

Un computer dell'ufficio che resta acceso durante l'orario di lavoro. Deve
avere un **IP fisso** sulla rete locale (riservalo dal router, o impostalo
manualmente). Non serve potente: il proxy è leggerissimo.

## 2. Installa il proxy in modalità condivisa

Su quella macchina lancia l'installer:

- **macOS:** `Installa (macOS).command` → alla domanda sul proxy fiscale scegli
  **2) Condiviso**. L'installer genera un token (o inseriscine uno tuo) e ti
  mostra i valori da mettere in Firestore.
- **Windows:** `Installa (Windows).bat` → segui le istruzioni per la modalità
  condivisa (imposta le variabili `PROXY_HOST=0.0.0.0` e `ITALRETAIL_TOKEN`
  nell'attività pianificata).

Apri sul firewall la **porta 8766** in entrata.

## 3. Configura Firestore (una volta)

Console Firebase → progetto **garden-river-conti-febed** → Firestore →
crea il documento **`config/fiscalizzazione`** con due campi stringa:

| Campo | Valore |
|---|---|
| `proxy_url` | `https://<ip-del-server>:8766` |
| `token` | il token generato dall'installer |

Da questo momento l'app (Calendario, Scontrino libero) usa automaticamente il
proxy condiviso. Se un giorno cambi macchina: aggiorni solo questo documento,
nessuna modifica sui dispositivi.

> Il documento è protetto dalle regole: i client possono **leggerlo** (serve
> all'app) ma non modificarlo. Il token si cambia solo da console.

## 4. Fai accettare il certificato su ogni dispositivo

Il proxy usa un certificato "self-signed": ogni dispositivo deve fidarsene una
volta. Due strade:

**A) Manuale (veloce, per pochi dispositivi)**
Da ogni dispositivo apri nel browser `https://<ip-del-server>:8766` e accetta
l'avviso di sicurezza ("Procedi comunque"). Vedrai una spunta verde. Fatto.
Va rifatto se il dispositivo cancella i dati del browser.

**B) Profilo di configurazione (stabile, per molti dispositivi)**
Distribuisci `proxy_cert.pem` come certificato attendibile:
- **iPhone/iPad:** invia il file `.pem` via AirDrop/email → Impostazioni →
  Profilo scaricato → Installa → poi Impostazioni → Generali → Info →
  Impostazioni certificati → attiva la fiducia completa.
- **Mac:** doppio clic sul `.pem` → Accesso Portachiavi → trascina in "Sistema"
  → doppio clic sul certificato → Fidati → "Fidati sempre".
- **Windows:** doppio clic → Installa certificato → Computer locale →
  "Autorità di certificazione radice attendibili".
- **Android:** Impostazioni → Sicurezza → Cifratura e credenziali → Installa
  un certificato → Certificato CA.

**C) Certificato vero (nessun avviso mai)**
Registra un sottodominio (es. `cassa.gardenhub.it`) che punta all'IP locale
del server e genera un certificato Let's Encrypt con challenge DNS. Il proxy
va configurato per usarlo al posto di `proxy_cert.pem`/`proxy_key.pem`.
È la soluzione più pulita ma richiede un po' di setup iniziale.

## 5. Assegna i permessi

Hub → Impostazioni → Permessi → seleziona l'operatore → sezione **Azioni** →
spunta / togli **"Può fiscalizzare"**. Di default tutti possono; togli il
permesso a chi non deve. La modifica ha effetto dal prossimo accesso.

## Registro degli scontrini

Ogni emissione riuscita finisce in **due** posti:
- Firestore, collezione `scontrini_fiscali` (scritta dal browser): operatore,
  dispositivo, importo, righe, ora.
- Sul disco del server, file `scontrini_emessi.jsonl` accanto al proxy: rete di
  sicurezza che non dipende dal browser.

## Tornare alla modalità "solo locale"

Rilancia l'installer sul singolo PC e scegli **1) Solo locale**; elimina il
documento `config/fiscalizzazione` da Firestore. L'app torna a usare
`https://localhost:8766` senza token.
