#!/usr/bin/env python3
"""
Proxy HTTPS per stampante Epson ePOS-Print — Garden River
Ascolta su 0.0.0.0:8765 (HTTPS) e inoltra alla stampante su HTTP.
"""
import ssl, os, urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

PRINTER_IP = "192.168.5.85"
PORT = 8765
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CERT = os.path.join(BASE_DIR, "proxy_cert.pem")
KEY  = os.path.join(BASE_DIR, "proxy_key.pem")

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
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, SOAPAction')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS, GET')

    def log_message(self, fmt, *args):
        pass  # silenzioso in background

if __name__ == '__main__':
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT, KEY)
    server = HTTPServer(('0.0.0.0', PORT), ProxyHandler)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    server.serve_forever()
