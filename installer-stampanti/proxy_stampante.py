#!/usr/bin/env python3
"""
Proxy HTTPS per stampante Epson ePOS-Print — Garden River
Ascolta su 127.0.0.1:8765 (HTTPS) e inoltra alla stampante su HTTP.
"""
import ssl, os, urllib.request, socket, ipaddress, base64
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler

PRINTER_IP = "192.168.5.85"
PORT = 8765
# Solo loopback: il browser che usa il proxy gira sulla stessa macchina.
HOST = os.environ.get("PROXY_HOST", "127.0.0.1")
# Origini web autorizzate a stampare tramite questo proxy.
ALLOWED_ORIGINS = {
    "https://gardenhub.it",
    "https://www.gardenhub.it",
    "http://localhost:8745",
    "http://127.0.0.1:8745",
}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CERT = os.path.join(BASE_DIR, "proxy_cert.pem")
KEY  = os.path.join(BASE_DIR, "proxy_key.pem")


# ── Sunmi / stampanti ESC/POS di rete (porta 9100) ────────────────────────────
# Le schermate della Hub generano XML Epson ePOS-Print. Per le stampanti ESC/POS
# (es. Sunmi 80mm) il proxy traduce quell'XML in comandi grezzi e li manda alla
# porta 9100. La Sunmi stampa in UTF-8 (accenti ed euro): niente ESC t / FS .
ESCPOS_PORT = 9100
# Colonne a tutta larghezza (carta 80mm): font A = 48, font B = 64 (a dimensione 1x)
COLS_FONT_A, COLS_FONT_B = 48, 64

def _tag(el):
    return el.tag.rsplit('}', 1)[-1]

def epos_to_escpos(xml_bytes):
    root = ET.fromstring(xml_bytes)
    out = bytearray(b'\x1b@')
    st = {'align': 'left', 'em': False, 'reverse': False, 'w': 1, 'h': 1, 'font': 'font_a'}
    ALIGN = {'left': 0, 'center': 1, 'right': 2}

    line_len = [0]  # caratteri gia' stampati sulla riga corrente

    def bool_attr(v):
        return str(v).lower() == 'true'

    for el in root.iter():
        t = _tag(el)
        if t == 'text':
            a = el.attrib
            txt = (el.text or '').replace('\r', '')
            # Riga in inverso che sta per chiudersi: riempila fino a tutta la larghezza
            if st['reverse'] and 'reverse' in a and not bool_attr(a['reverse']) and txt.startswith('\n'):
                cols = (COLS_FONT_B if st['font'] == 'font_b' else COLS_FONT_A) // st['w']
                if 0 < line_len[0] < cols:
                    out += b' ' * (cols - line_len[0])
            if 'align' in a and a['align'] != st['align']:
                st['align'] = a['align']; out += b'\x1ba' + bytes([ALIGN.get(st['align'], 0)])
            if 'font' in a and a['font'] != st['font']:
                st['font'] = a['font']; out += b'\x1bM' + bytes([1 if st['font'] == 'font_b' else 0])
            if 'em' in a and bool_attr(a['em']) != st['em']:
                st['em'] = bool_attr(a['em']); out += b'\x1bE' + bytes([1 if st['em'] else 0])
            if 'reverse' in a and bool_attr(a['reverse']) != st['reverse']:
                st['reverse'] = bool_attr(a['reverse']); out += b'\x1dB' + bytes([1 if st['reverse'] else 0])
            if 'width' in a or 'height' in a:
                st['w'] = max(1, min(8, int(a.get('width', st['w']))))
                st['h'] = max(1, min(8, int(a.get('height', st['h']))))
                out += b'\x1d!' + bytes([((st['w'] - 1) << 4) | (st['h'] - 1)])
            out += txt.encode('utf-8')
            if '\n' in txt:
                line_len[0] = len(txt.rsplit('\n', 1)[1])
            else:
                line_len[0] += len(txt)
        elif t == 'feed':
            out += b'\n' * max(1, int(el.attrib.get('line', 1)))
            line_len[0] = 0
        elif t == 'image':
            w = int(el.attrib['width']); h = int(el.attrib['height'])
            data = base64.b64decode((el.text or '').strip())
            rb = (w + 7) // 8
            out += b'\x1d' + b'v0\x00' + bytes([rb & 255, rb >> 8, h & 255, h >> 8]) + data[:rb * h]
        elif t == 'cut':
            out += b'\x1dVB\x00'
    return bytes(out)

def send_escpos(ip, data):
    # Solo indirizzi di rete locale: il proxy non deve fare da ponte verso Internet.
    if not ipaddress.ip_address(ip).is_private:
        raise ValueError('IP non di rete locale')
    with socket.create_connection((ip, ESCPOS_PORT), timeout=5) as s:
        s.sendall(data)

class ProxyHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self._cors()
        self.end_headers()
        self.wfile.write(b'<h2>&#10003; Proxy stampante attivo</h2><p>Certificato accettato. Puoi chiudere.</p>')

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        u = urlparse(self.path)
        if u.path == '/sunmi':
            try:
                ip = parse_qs(u.query).get('ip', [''])[0]
                send_escpos(ip, epos_to_escpos(body))
                self.send_response(200); self._cors()
                self.send_header('Content-Type', 'text/xml; charset=utf-8'); self.end_headers()
                self.wfile.write(b'<response success="true" code=""/>')
            except Exception as e:
                self.send_response(502); self._cors(); self.end_headers()
                self.wfile.write(str(e).encode())
            return
        req = urllib.request.Request(
            f"http://{PRINTER_IP}{self.path}",
            data=body, method='POST'
        )
        for h in ('Content-Type', 'SOAPAction'):
            if self.headers.get(h):
                req.add_header(h, self.headers[h])
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
            self.send_response(200)
            self._cors()
            self.send_header('Content-Type', 'text/xml; charset=utf-8')
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_response(502)
            self._cors()
            self.end_headers()
            self.wfile.write(str(e).encode())

    def _cors(self):
        origin = self.headers.get('Origin')
        if origin in ALLOWED_ORIGINS:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, SOAPAction')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS, GET')
        self.send_header('Access-Control-Allow-Private-Network', 'true')

    def log_message(self, fmt, *args):
        pass  # silenzioso in background

if __name__ == '__main__':
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT, KEY)
    server = HTTPServer((HOST, PORT), ProxyHandler)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    server.serve_forever()
