#!/usr/bin/env python3
"""
Proxy HTTPS per Registratore Telematico ItalRetail (Start RT) — Garden River
Ascolta su 127.0.0.1:8766 (HTTPS) e inoltra alla cassa via Raw Socket TCP.

Due modalita':
  • "solo locale" (default): PROXY_HOST=127.0.0.1, un PC = una postazione.
  • "condiviso": PROXY_HOST=0.0.0.0, raggiungibile da tutti i dispositivi
    dell'ufficio. In questo caso serve un TOKEN (ITALRETAIL_TOKEN o campo
    "token" in italretail_config.json): ogni richiesta a /scontrino,
    /test-connessione, /configurazione deve portare l'header
    Authorization: Bearer <token>, altrimenti risponde 401.

Ogni emissione viene annotata in scontrini_emessi.jsonl (giornale locale
di sicurezza; la copia ufficiale del registro la scrive il browser su
Firestore).

IP/porta/timeout sono configurabili dalla pagina Impostazioni > Fiscalizzazione
e vengono salvati QUI, su disco (italretail_config.json accanto a questo file),
non nel localStorage del browser: aperta come file:// (non da un indirizzo
web), molti browser — Safari in particolare — non persistono davvero il
localStorage, quindi il browser da solo non e' una fonte affidabile per
un'impostazione che deve "restare" tra una fiscalizzazione e l'altra.

Endpoint GET /configurazione: restituisce la configurazione salvata.
Endpoint POST /configurazione, corpo JSON: { "ip": "192.168.5.4", "porta": 9100, "timeout": 5 }
  Salva la configurazione su disco. Risposta: { "ok": true } o { "ok": false, "errore": "..." }

Endpoint POST /scontrino, corpo JSON:
{
  "ip": "...", "porta": 9100, "timeout": 5,   // opzionali: sovrascrivono la
                                                // configurazione salvata solo
                                                // per questa singola richiesta
  "righe": [ { "categoria": "soggiorno", "descrizione": "Soggiorno", "prezzo_eur": 100.0, "quantita": 1 }, ... ],
  "metodo_pagamento": "contanti"
}
Risposta JSON: { "ok": true } oppure { "ok": false, "errore": "..." }

Endpoint POST /test-connessione, stesso corpo JSON ma senza "righe"/"metodo_pagamento":
apre e chiude la socket senza inviare alcun comando (nessun effetto fiscale),
utile per verificare IP/porta dalla pagina Impostazioni.
Risposta JSON: { "ok": true } oppure { "ok": false, "errore": "..." }
"""
import datetime
import hmac
import json
import os
import ssl
from http.server import HTTPServer, BaseHTTPRequestHandler

from italretail_rt import RegistratoreItalRetail, RigaVendita, ItalRetailError, IP_DEFAULT, PORTA_DEFAULT, TIMEOUT_SOCKET

PORT = 8766
# Interfaccia di ascolto:
#   • "127.0.0.1" (default): solo la stessa macchina del proxy — installazione
#     classica "un PC = una postazione".
#   • "0.0.0.0": raggiungibile da tutti i dispositivi della rete d'ufficio —
#     modalita' "proxy condiviso". In questo caso il TOKEN e' OBBLIGATORIO
#     (v. controllo all'avvio) e ogni richiesta deve portarlo nell'header
#     Authorization: Bearer <token>.
# Si imposta con la variabile d'ambiente PROXY_HOST.
HOST = os.environ.get("PROXY_HOST", "127.0.0.1")
# Solo queste origini web possono usare il proxy: la Hub in produzione e la
# copia in locale ("Apri Hub in locale.command", porta 8745). Una pagina
# qualsiasi aperta nello stesso browser NON puo' piu' emettere scontrini.
ALLOWED_ORIGINS = {
    "https://gardenhub.it",
    "https://www.gardenhub.it",
    "http://localhost:8745",
    "http://127.0.0.1:8745",
}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CERT = os.path.join(BASE_DIR, "proxy_cert.pem")
KEY = os.path.join(BASE_DIR, "proxy_key.pem")
CONFIG_PATH = os.path.join(BASE_DIR, "italretail_config.json")
# Giornale locale delle emissioni (rete di sicurezza: la copia "ufficiale" del
# registro va su Firestore, scritta dal browser dopo ogni emissione riuscita —
# qui teniamo comunque una traccia append-only che non dipende dal browser).
JOURNAL_PATH = os.path.join(BASE_DIR, "scontrini_emessi.jsonl")


def carica_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                dati = json.load(f)
            return {
                "ip": dati.get("ip") or IP_DEFAULT,
                "porta": int(dati.get("porta") or PORTA_DEFAULT),
                "timeout": float(dati.get("timeout") or TIMEOUT_SOCKET),
                "token": (dati.get("token") or "").strip(),
            }
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    return {"ip": IP_DEFAULT, "porta": PORTA_DEFAULT, "timeout": TIMEOUT_SOCKET, "token": ""}


def salva_config(config: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


_config = carica_config()
# Il token puo' arrivare anche da variabile d'ambiente (ITALRETAIL_TOKEN):
# comodo per l'installer in modalita' "server", che non deve scrivere il
# segreto in chiaro nello script.
TOKEN = os.environ.get("ITALRETAIL_TOKEN", "").strip() or _config.get("token", "")


def _is_loopback(host: str) -> bool:
    return host in ("127.0.0.1", "::1", "localhost")


def _giornale(riga: dict) -> None:
    """Append best-effort al giornale locale. Non deve mai far fallire la richiesta."""
    try:
        riga = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), **riga}
        with open(JOURNAL_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(riga, ensure_ascii=False) + "\n")
    except OSError:
        pass


class ProxyHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def _auth_ok(self) -> bool:
        # Nessun token configurato E ascolto solo su loopback → installazione
        # classica single-PC, si accetta senza header (retrocompatibilita').
        if not TOKEN and _is_loopback(HOST):
            return True
        header = self.headers.get('Authorization', '')
        prefix = 'Bearer '
        if not header.startswith(prefix):
            return False
        return hmac.compare_digest(header[len(prefix):].strip(), TOKEN)

    def _nega_auth(self):
        self.send_response(401)
        self._cors()
        self.send_header('WWW-Authenticate', 'Bearer')
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps({"ok": False, "errore": "Autorizzazione mancante o non valida"}).encode('utf-8'))

    def do_GET(self):
        if self.path == '/configurazione':
            if not self._auth_ok():
                self._nega_auth()
                return
            self._json_response(200, {"ok": True, **{k: v for k, v in _config.items() if k != 'token'}})
            return
        # Pagina di cortesia per accettare il certificato: sempre accessibile.
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self._cors()
        self.end_headers()
        self.wfile.write(b'<h2>&#10003; Proxy ItalRetail attivo</h2><p>Certificato accettato. Puoi chiudere.</p>')

    def do_POST(self):
        if self.path not in ('/scontrino', '/test-connessione', '/configurazione'):
            self._json_response(404, {"ok": False, "errore": "Endpoint sconosciuto"})
            return

        if not self._auth_ok():
            self._nega_auth()
            return

        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._json_response(400, {"ok": False, "errore": "JSON non valido"})
            return

        if self.path == '/configurazione':
            self._salva_configurazione(payload)
            return

        try:
            rt = self._costruisci_rt(payload)
        except (TypeError, ValueError) as e:
            self._json_response(400, {"ok": False, "errore": f"Parametri connessione non validi: {e}"})
            return

        if self.path == '/test-connessione':
            risultato = rt.verifica_connessione()
            self._json_response(200, {"ok": risultato.ok, "errore": risultato.errore})
            return

        try:
            righe = [
                RigaVendita(
                    categoria=r['categoria'],
                    descrizione=r.get('descrizione', ''),
                    prezzo_eur=float(r['prezzo_eur']),
                    quantita=int(r.get('quantita', 1)),
                )
                for r in payload.get('righe', [])
            ]
            metodo_pagamento = payload['metodo_pagamento']
        except (KeyError, TypeError, ValueError) as e:
            self._json_response(400, {"ok": False, "errore": f"Corpo richiesta non valido: {e}"})
            return

        dry_run = bool(payload.get('dry_run', False))
        totale = round(sum(r.prezzo_eur * r.quantita for r in righe), 2)
        voce_giornale = {
            "operatore": (payload.get('operatore') or '').strip() or None,
            "dispositivo": (payload.get('dispositivo') or '').strip() or self.client_address[0],
            "totale_eur": totale,
            "metodo_pagamento": metodo_pagamento,
            "n_righe": len(righe),
            "dry_run": dry_run,
        }
        try:
            risultato = rt.invia_scontrino(righe, metodo_pagamento, dry_run=dry_run)
        except ItalRetailError as e:
            _giornale({**voce_giornale, "ok": False, "errore": str(e)})
            self._json_response(200, {"ok": False, "errore": str(e)})
            return

        _giornale({**voce_giornale, "ok": bool(risultato.ok), "errore": risultato.errore or None,
                   "dettagli": risultato.dettagli})
        self._json_response(200, {"ok": risultato.ok, "errore": risultato.errore, "dettagli": risultato.dettagli})

    def _salva_configurazione(self, payload: dict):
        global _config
        ip = (payload.get('ip') or '').strip()
        if not ip:
            self._json_response(400, {"ok": False, "errore": "IP mancante"})
            return
        try:
            nuova_config = {
                "ip": ip,
                "porta": int(payload.get('porta') or PORTA_DEFAULT),
                "timeout": float(payload.get('timeout') or TIMEOUT_SOCKET),
                "token": _config.get("token", ""),  # il token non si tocca da qui
            }
        except (TypeError, ValueError) as e:
            self._json_response(400, {"ok": False, "errore": f"Parametri non validi: {e}"})
            return
        _config = nuova_config
        try:
            salva_config(_config)
        except OSError as e:
            self._json_response(500, {"ok": False, "errore": f"Impossibile salvare su disco: {e}"})
            return
        self._json_response(200, {"ok": True, **{k: v for k, v in _config.items() if k != 'token'}})

    def _costruisci_rt(self, payload: dict) -> RegistratoreItalRetail:
        ip = (payload.get('ip') or '').strip() or _config['ip']
        porta = int(payload['porta']) if payload.get('porta') not in (None, '') else _config['porta']
        timeout = float(payload['timeout']) if payload.get('timeout') not in (None, '') else _config['timeout']
        return RegistratoreItalRetail(ip=ip, porta=porta, timeout=timeout)

    def _json_response(self, status: int, payload: dict):
        body = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self._cors()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        origin = self.headers.get('Origin')
        if origin in ALLOWED_ORIGINS:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS, GET')

    def log_message(self, fmt, *args):
        pass  # silenzioso in background


if __name__ == '__main__':
    # In modalita' "proxy condiviso" (ascolto non-loopback) il token e'
    # obbligatorio: senza, qualunque dispositivo della rete potrebbe emettere
    # scontrini. Meglio non partire affatto che partire insicuri.
    if not _is_loopback(HOST) and not TOKEN:
        raise SystemExit(
            "ERRORE: PROXY_HOST=%s (rete) ma nessun token impostato.\n"
            "Imposta la variabile d'ambiente ITALRETAIL_TOKEN oppure il campo\n"
            "\"token\" in italretail_config.json, poi riavvia." % HOST
        )
    modo = "solo locale (127.0.0.1)" if _is_loopback(HOST) else "condiviso su %s" % HOST
    print("Proxy ItalRetail — modalita': %s — token: %s" % (modo, "si" if TOKEN else "no"))
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT, KEY)
    server = HTTPServer((HOST, PORT), ProxyHandler)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    server.serve_forever()
