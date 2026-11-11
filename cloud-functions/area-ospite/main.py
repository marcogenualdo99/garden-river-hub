"""Area ospite — mini-pannello Garden Hub.

Endpoint HTTP pubblico usato dalla pagina https://gardenhub.it/area-ospite/?t=
<token>: un unico link per prenotazione, pensato per contenere nel tempo più
sezioni (Ristorazione, Animazione, Info utili, Navetta, Assistenza). Per ora
è operativa solo la sezione "Servizio navetta".

Stesso schema del check-in online (vedi cloud-functions/checkin-online): il
browser dell'ospite non tocca mai Firestore, tutto passa da qui con l'Admin
SDK. Il collegamento token -> prenotazione vive SOLO nella collezione
`area_ospite_links/{token}`, negata in lettura a tutti i client dalle regole
Firestore.

Azioni (campo "azione" nel corpo JSON):
  - carica          : { token }
        -> riepilogo sanificato della prenotazione (nome, telefono, alloggio)
           + l'eventuale ombrellone/spiaggia già assegnati dal Calendario
           + l'elenco delle spiagge e degli autisti configurati (per i due
           menu a tendina) + l'eventuale accesso Ristorazione (famiglia/
           codice, se il trattamento prevede pasti) + le richieste navetta
           già fatte oggi da questo stesso ospite (per mostrargliene lo
           stato)
  - navetta_prenota : { token, nome, telefono, alloggio_nome, spiaggia_nome,
                         autista_nome, orario }
        -> valida l'orario (fascia attiva + preavviso minimo, v.
           PREAVVISO_MINIMO_MINUTI) e scrive la richiesta in
           `navetta_prenotazioni` (data = oggi, stato "in_attesa",
           autista_nome assegnato in seguito dalla dashboard autisti)
"""

import json
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import firebase_admin
from firebase_admin import firestore
import functions_framework

if not firebase_admin._apps:
    firebase_admin.initialize_app()

ALLOWED_ORIGINS = {'https://gardenhub.it', 'https://www.gardenhub.it'}
TZ_ROMA = ZoneInfo('Europe/Rome')

# Fasce attive e passo degli orari — stessi orari già stampati sul ticket
# spiaggia (spiaggia/index.html): 09:00–13:00 e 15:30–19:00, ogni 15'.
FASCE_NAVETTA = (('09:00', '13:00'), ('15:30', '19:00'))
PASSO_MINUTI = 15
# Preavviso minimo richiesto: un orario è prenotabile solo se dista almeno
# così tanti minuti da adesso (dà tempo all'autista di organizzarsi).
PREAVVISO_MINIMO_MINUTI = 25

MAX_TESTO = 120


# ── CORS / risposta ────────────────────────────────────────────────────────

def _cors_headers(origin):
    allow = origin if origin in ALLOWED_ORIGINS else 'https://gardenhub.it'
    return {
        'Access-Control-Allow-Origin':  allow,
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
    }


def _json(origin, payload, status=200):
    return (json.dumps(payload), status,
            {**_cors_headers(origin), 'Content-Type': 'application/json'})


def _now_ms():
    return int(time.time() * 1000)


def _now_iso():
    return time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()) + 'Z'


def _oggi_iso():
    return datetime.now(TZ_ROMA).strftime('%Y-%m-%d')


def _s(v, max_len=MAX_TESTO):
    return str(v).strip()[:max_len] if v is not None else ''


# ── token / prenotazione ───────────────────────────────────────────────────

def _token_valido(token):
    return bool(re.fullmatch(r'[a-f0-9]{16,64}', token or ''))


def _risolvi_token(db, token):
    """Ritorna (pren_ref, pren_dict) oppure (None, None)."""
    if not _token_valido(token):
        return None, None
    link_ref = db.collection('area_ospite_links').document(token)
    snap = link_ref.get()
    if not snap.exists:
        return None, None
    d = snap.to_dict() or {}
    scade_il = d.get('scade_il') or 0
    if scade_il and scade_il < _now_ms():
        try:
            link_ref.delete()           # link scaduto: pulizia opportunistica
        except Exception:
            pass
        return None, None
    pren_id = d.get('prenId')
    if not pren_id:
        return None, None
    pren_ref = db.collection('prenotazioni').document(pren_id)
    pren = pren_ref.get()
    if not pren.exists:
        return None, None
    return pren_ref, (pren.to_dict() or {})


def _spiagge_disponibili(db):
    """Elenco spiagge configurate nel modulo Spiaggia (beach_spiagge), per il
    menu a tendina lato ospite — niente più campo libero."""
    try:
        return [
            {'id': d.id, 'nome': _s((d.to_dict() or {}).get('nome')) or d.id}
            for d in db.collection('beach_spiagge').stream()
        ]
    except Exception as e:
        print(f'Lettura beach_spiagge non riuscita: {e}')
        return []


def _autisti_elenco(db):
    """Autisti configurati (collezione navetta_autisti, gestita dalla
    dashboard Navetta) — sono sempre tutti disponibili, nessuna gestione
    giorno per giorno. Il cliente può sempre lasciare 'chiunque disponibile'."""
    try:
        return [
            {'id': d.id, 'nome': _s((d.to_dict() or {}).get('nome')) or d.id}
            for d in db.collection('navetta_autisti').stream()
        ]
    except Exception as e:
        print(f'Lettura navetta_autisti non riuscita: {e}')
        return []


def _ristorazione_disponibile(db, pren_id):
    """Famiglia Ristorazione collegata a questa prenotazione (creata in
    automatico dal Calendario quando il trattamento è PC/MP — v.
    sincronizzaFamigliaRistorazione in calendario/index.html). Cerca prima
    per id diretto (convenzione 'cal_<prenId>'), poi per campo (nel caso sia
    stata collegata a mano con un id diverso). None se il soggiorno non
    include pasti o la sincronizzazione non è mai scattata."""
    try:
        f = None
        diretta = db.collection('famiglie_ristorazione').document(f'cal_{pren_id}').get()
        if diretta.exists:
            f = diretta.to_dict() or {}
        else:
            q = (db.collection('famiglie_ristorazione')
                   .where('calendario_prenotazione_id', '==', pren_id)
                   .limit(1))
            docs = list(q.stream())
            if docs:
                f = docs[0].to_dict() or {}
        if not f:
            return None
        codice = _s(f.get('codice'))
        trattamento = _s(f.get('trattamento'))
        if not codice or trattamento not in ('PC', 'MP'):
            return None
        return {'codice': codice, 'trattamento': trattamento}
    except Exception as e:
        print(f'Lettura famiglia ristorazione non riuscita: {e}')
        return None


def _navetta_oggi_cliente(db, pren_id):
    """Le richieste navetta di oggi fatte da questo stesso ospite (per
    mostrargli lo stato della corsa nel suo pannello — l'ospite non ha
    accesso diretto a Firestore, può vederle solo tramite questa azione)."""
    try:
        q = (db.collection('navetta_prenotazioni')
               .where('prenId', '==', pren_id)
               .where('data', '==', _oggi_iso()))
        out = [
            {
                'id': d.id,
                'orario': _s((d.to_dict() or {}).get('orario')),
                'stato': _s((d.to_dict() or {}).get('stato')) or 'in_attesa',
                'autista_nome': _s((d.to_dict() or {}).get('autista_nome')),
            }
            for d in q.stream()
        ]
        out.sort(key=lambda x: x['orario'])
        return out
    except Exception as e:
        print(f'Lettura navetta_prenotazioni cliente non riuscita: {e}')
        return []


def _spiaggia_assegnata(db, pren_id):
    """Ombrellone/spiaggia già posizionati dal Calendario per questa
    prenotazione (collezione beach_prenotazioni, campo
    calendario_prenotazione_id — v. calendario/index.html). None se assente."""
    try:
        q = (db.collection('beach_prenotazioni')
               .where('calendario_prenotazione_id', '==', pren_id)
               .limit(1))
        docs = list(q.stream())
        if not docs:
            return None
        b = docs[0].to_dict() or {}
        ombrellone = _s(b.get('ombrellone'))
        if not ombrellone:
            return None
        nome_spiaggia = b.get('spiaggia_id') or ''
        spiaggia_id = b.get('spiaggia_id')
        if spiaggia_id:
            s = db.collection('beach_spiagge').document(spiaggia_id).get()
            if s.exists:
                nome_spiaggia = _s((s.to_dict() or {}).get('nome')) or nome_spiaggia
        return {'spiaggia_nome': nome_spiaggia, 'ombrellone': ombrellone}
    except Exception as e:
        print(f'Lettura spiaggia assegnata non riuscita: {e}')
        return None


# ── orari navetta ──────────────────────────────────────────────────────────

def _slot_validi():
    """Elenco 'HH:MM' di tutte le fasce, passo PASSO_MINUTI (bordo incluso)."""
    out = []
    for inizio, fine in FASCE_NAVETTA:
        h0, m0 = map(int, inizio.split(':'))
        h1, m1 = map(int, fine.split(':'))
        t = h0 * 60 + m0
        tf = h1 * 60 + m1
        while t <= tf:
            out.append(f'{t // 60:02d}:{t % 60:02d}')
            t += PASSO_MINUTI
    return out


def _minuti_da_ora(orario):
    """Minuti tra adesso (ora di Roma) e l'orario 'HH:MM' passato, oggi."""
    h, m = map(int, orario.split(':'))
    ora = datetime.now(TZ_ROMA)
    target = ora.replace(hour=h, minute=m, second=0, microsecond=0)
    return (target - ora).total_seconds() / 60


def _orario_valido(orario):
    if not bool(re.fullmatch(r'[0-2]\d:[0-5]\d', orario or '')) or orario not in _slot_validi():
        return False
    return _minuti_da_ora(orario) >= PREAVVISO_MINIMO_MINUTI


# ── azioni ─────────────────────────────────────────────────────────────────

def _azione_carica(db, origin, data):
    pren_ref, p = _risolvi_token(db, data.get('token'))
    if not p:
        return _json(origin, {'ok': False, 'errore': 'link_non_valido'}, 404)

    return _json(origin, {
        'ok': True,
        'prenotazione': {
            'nome':          _s(p.get('nome')),
            'telefono':      _s(p.get('tel')),
            'alloggio_nome': _s(p.get('alloggio_nome')),
            'checkin':       _s(p.get('checkin')),
            'checkout':      _s(p.get('checkout')),
        },
        'spiaggia': _spiaggia_assegnata(db, pren_ref.id),
        'spiagge': _spiagge_disponibili(db),
        'autisti': _autisti_elenco(db),
        'ristorazione': _ristorazione_disponibile(db, pren_ref.id),
        'navetta_oggi': _navetta_oggi_cliente(db, pren_ref.id),
        'fasce': [{'dal': a, 'al': b} for a, b in FASCE_NAVETTA],
        'preavviso_minimo_minuti': PREAVVISO_MINIMO_MINUTI,
    })


def _azione_navetta_prenota(db, origin, data):
    pren_ref, p = _risolvi_token(db, data.get('token'))
    if not p:
        return _json(origin, {'ok': False, 'errore': 'link_non_valido'}, 404)

    orario = _s(data.get('orario'), 5)
    if not _orario_valido(orario):
        return _json(origin, {'ok': False, 'errore': 'orario_non_valido'}, 400)

    nome = _s(data.get('nome')) or _s(p.get('nome'))
    telefono = _s(data.get('telefono')) or _s(p.get('tel'))
    alloggio_nome = _s(data.get('alloggio_nome')) or _s(p.get('alloggio_nome'))
    spiaggia_nome = _s(data.get('spiaggia_nome'))
    autista_nome = _s(data.get('autista_nome'))  # facoltativo: il cliente lo sceglie se lo sa
    if not nome or not telefono:
        return _json(origin, {'ok': False, 'errore': 'dati_incompleti'}, 400)

    doc = {
        'prenId':        pren_ref.id,
        'alloggio_nome': alloggio_nome,
        'nome':          nome,
        'telefono':      telefono,
        'spiaggia_nome': spiaggia_nome,
        'data':          _oggi_iso(),
        'orario':        orario,
        'stato':         'in_attesa',
        'autista_nome':  autista_nome or None,
        'creato_il':     _now_iso(),
    }
    ref = db.collection('navetta_prenotazioni').document()
    ref.set(doc)
    return _json(origin, {'ok': True, 'id': ref.id})


AZIONI = {
    'carica':          _azione_carica,
    'navetta_prenota': _azione_navetta_prenota,
}


@functions_framework.http
def area_ospite(request):
    origin = request.headers.get('Origin', '')

    if request.method == 'OPTIONS':
        return ('', 204, _cors_headers(origin))
    if request.method != 'POST':
        return _json(origin, {'ok': False, 'errore': 'metodo_non_permesso'}, 405)

    data = request.get_json(silent=True) or {}
    handler = AZIONI.get(data.get('azione'))
    if not handler:
        return _json(origin, {'ok': False, 'errore': 'azione_non_valida'}, 400)

    try:
        return handler(firestore.client(), origin, data)
    except Exception as e:
        print(f'Errore azione {data.get("azione")}: {e}')
        return _json(origin, {'ok': False, 'errore': 'errore_interno'}, 500)
