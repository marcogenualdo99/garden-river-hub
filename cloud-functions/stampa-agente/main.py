"""Agente di stampa — Garden Hub.

Coda di stampa per i dispositivi senza proxy locale (iPad, iPhone) o quando il
proxy non e' acceso. Il browser (utente loggato) scrive un lavoro in
`coda_stampa/{id}` con l'XML ePOS; l'app Android "Agente Stampa" (sul Sunmi V2
sempre acceso) chiama questa funzione ogni pochi secondi:

  - prendi : { }                        -> { ok, lavori:[{id, ip, dati(base64 ESC/POS)}] }
  - esito  : { id, ok, errore? }        -> { ok }

Autenticazione: intestazione `X-Agente-Token` uguale alla variabile d'ambiente
AGENTE_TOKEN della funzione. Il client web non chiama mai questa funzione.
La traduzione XML ePOS -> ESC/POS e' la stessa di proxy_stampante.py.
Solo IP di rete locale (la stampante e' sulla LAN dell'agente).
"""
import base64
import hmac
import ipaddress
import json
import os
import time
import xml.etree.ElementTree as ET

import firebase_admin
from firebase_admin import firestore
import functions_framework

if not firebase_admin._apps:
    firebase_admin.initialize_app()

MAX_ETA_S = 600          # lavori piu' vecchi di 10 minuti non si stampano piu'
MAX_PER_GIRO = 5
COLS_FONT_A, COLS_FONT_B = 48, 64


def _tag(el):
    return el.tag.rsplit('}', 1)[-1]


def epos_to_escpos(xml_bytes):
    root = ET.fromstring(xml_bytes)
    out = bytearray(b'\x1b@')
    st = {'align': 'left', 'em': False, 'reverse': False, 'w': 1, 'h': 1, 'font': 'font_a'}
    ALIGN = {'left': 0, 'center': 1, 'right': 2}
    line_len = [0]

    def bool_attr(v):
        return str(v).lower() == 'true'

    for el in root.iter():
        t = _tag(el)
        if t == 'text':
            a = el.attrib
            txt = (el.text or '').replace('\r', '')
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


def _risposta(payload, code=200):
    return (json.dumps(payload), code, {'Content-Type': 'application/json'})


@functions_framework.http
def stampa_agente(request):
    if request.method != 'POST':
        return _risposta({'ok': False, 'errore': 'metodo'}, 405)
    atteso = os.environ.get('AGENTE_TOKEN', '')
    dato = request.headers.get('X-Agente-Token', '')
    if not atteso or len(atteso) < 16 or not hmac.compare_digest(atteso, dato):
        return _risposta({'ok': False, 'errore': 'non autorizzato'}, 401)
    body = request.get_json(silent=True) or {}
    azione = body.get('azione')
    db = firestore.client()
    col = db.collection('coda_stampa')

    if azione == 'prendi':
        adesso = time.time()
        lavori = []
        for snap in col.where('stato', '==', 'in_coda').limit(20).stream():
            if len(lavori) >= MAX_PER_GIRO:
                break
            d = snap.to_dict() or {}
            if adesso - float(d.get('creato_ts', 0)) > MAX_ETA_S:
                snap.reference.update({'stato': 'scaduta'})
                continue
            try:
                ip = str(d.get('ip', ''))
                if not ipaddress.ip_address(ip).is_private:
                    raise ValueError('IP non locale')
                dati = base64.b64encode(epos_to_escpos(str(d.get('xml', '')).encode('utf-8'))).decode()
            except Exception as e:
                snap.reference.update({'stato': 'fallita', 'errore': 'lavoro non valido: %s' % e})
                continue

            @firestore.transactional
            def prendi(tx, ref):
                s = ref.get(transaction=tx)
                if (s.to_dict() or {}).get('stato') != 'in_coda':
                    return False
                tx.update(ref, {'stato': 'in_invio', 'preso_ts': adesso})
                return True

            if prendi(db.transaction(), snap.reference):
                lavori.append({'id': snap.id, 'ip': ip, 'dati': dati})
        return _risposta({'ok': True, 'lavori': lavori})

    if azione == 'esito':
        jid = str(body.get('id', ''))
        if not jid or '/' in jid:
            return _risposta({'ok': False, 'errore': 'id'}, 400)
        ok = body.get('ok') is True
        col.document(jid).update({
            'stato': 'ok' if ok else 'fallita',
            'errore': '' if ok else str(body.get('errore', ''))[:200],
            'finito_ts': time.time(),
        })
        return _risposta({'ok': True})

    return _risposta({'ok': False, 'errore': 'azione sconosciuta'}, 400)
