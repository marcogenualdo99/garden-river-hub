#!/usr/bin/env python3
"""
Proxy HTTPS per Registratore Telematico ItalRetail (Start RT) — Garden River
Ascolta su 0.0.0.0:8766 (HTTPS) e inoltra alla cassa via Raw Socket TCP.

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
import json
import os
import ssl
from http.server import HTTPServer, BaseHTTPRequestHandler

from italretail_rt import RegistratoreItalRetail, RigaVendita, ItalRetailError, IP_DEFAULT, PORTA_DEFAULT, TIMEOUT_SOCKET

PORT = 8766
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CERT = os.path.join(BASE_DIR, "proxy_cert.pem")
KEY = os.path.join(BASE_DIR, "proxy_key.pem")
CONFIG_PATH = os.path.join(BASE_DIR, "italretail_config.json")


def carica_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                dati = json.load(f)
            return {
                "ip": dati.get("ip") or IP_DEFAULT,
                "porta": int(dati.get("porta") or PORTA_DEFAULT),
                "timeout": float(dati.get("timeout") or TIMEOUT_SOCKET),
            }
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    return {"ip": IP_DEFAULT, "porta": PORTA_DEFAULT, "timeout": TIMEOUT_SOCKET}


def salva_config(config: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


_config = carica_config()


class ProxyHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == '/configurazione':
            self._json_response(200, {"ok": True, **_config})
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self._cors()
        self.end_headers()
        self.wfile.write(b'<h2>&#10003; Proxy ItalRetail attivo</h2><p>Certificato accettato. Puoi chiudere.</p>')

    def do_POST(self):
        if self.path not in ('/scontrino', '/test-connessione', '/configurazione'):
            self._json_response(404, {"ok": False, "errore": "Endpoint sconosciuto"})
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
        try:
            risultato = rt.invia_scontrino(righe, metodo_pagamento, dry_run=dry_run)
        except ItalRetailError as e:
            self._json_response(200, {"ok": False, "errore": str(e)})
            return

        self._json_response(200, {"ok": risultato.ok, "errore": risultato.errore, "dettagli": risultato.dettagli})

    def _salva_configurazione(self, payload: dict):
        ip = (payload.get('ip') or '').strip()
        if not ip:
            self._json_response(400, {"ok": False, "errore": "IP mancante"})
            return
        try:
            nuova_config = {
                "ip": ip,
                "porta": int(payload.get('porta') or PORTA_DEFAULT),
                "timeout": float(payload.get('timeout') or TIMEOUT_SOCKET),
            }
        except (TypeError, ValueError) as e:
            self._json_response(400, {"ok": False, "errore": f"Parametri non validi: {e}"})
            return
        global _config
        _config = nuova_config
        try:
            salva_config(_config)
        except OSError as e:
            self._json_response(500, {"ok": False, "errore": f"Impossibile salvare su disco: {e}"})
            return
        self._json_response(200, {"ok": True, **_config})

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
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS, GET')

    def log_message(self, fmt, *args):
        pass  # silenzioso in background


if __name__ == '__main__':
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT, KEY)
    server = HTTPServer(('0.0.0.0', PORT), ProxyHandler)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    server.serve_forever()
