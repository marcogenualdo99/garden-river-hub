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
  - contenuti       : { token } -> testi/foto gestiti dall'Hub (Area ospite)
  - navetta_stato   : { token } -> solo le richieste di oggi (polling leggero)
  - navetta_modifica_orario : { token, id, orario } -> sposta una corsa
  - navetta_prenota : { token, nome, telefono, alloggio_nome, spiaggia_nome,
                         autista_nome, orario }
        -> valida l'orario (fascia attiva + preavviso minimo, v.
           preavviso minimo da impostazioni/navetta) e scrive la richiesta in
           `navetta_prenotazioni` (data = oggi, stato "in_attesa",
           autista_nome assegnato in seguito dalla dashboard autisti)
"""

import json
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import firebase_admin
from google.api_core.exceptions import AlreadyExists
from firebase_admin import firestore
import functions_framework

if not firebase_admin._apps:
    firebase_admin.initialize_app()

ALLOWED_ORIGINS = {'https://gardenhub.it', 'https://www.gardenhub.it'}
TZ_ROMA = ZoneInfo('Europe/Rome')

# Valori di default della navetta: si cambiano da Hub > Navetta > Impostazioni
# (doc Firestore `impostazioni/navetta`). Fasce = stesse del ticket spiaggia.
NAVETTA_DEFAULT = {
    'fasce': [{'dal': '09:00', 'al': '13:00'}, {'dal': '15:30', 'al': '19:00'}],
    'passo_minuti': 15,
    # Un orario e' prenotabile solo se dista almeno cosi' tanti minuti da adesso.
    'preavviso_minimo_minuti': 25,
    # Il cliente puo' spostare una corsa solo se mancano almeno cosi' tanti minuti.
    'preavviso_modifica_minuti': 25,
}
SERVIZI_FOTO = ('home', 'navetta', 'ristorazione', 'animazione', 'info', 'assistenza')

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


# ── configurazione (Firestore `impostazioni/...`, scritta dall'Hub) ──────────

def _cfg_navetta(db):
    cfg = dict(NAVETTA_DEFAULT)
    try:
        snap = db.collection('impostazioni').document('navetta').get()
        d = snap.to_dict() or {} if snap.exists else {}
        fasce = []
        for f in d.get('fasce') or []:
            dal, al = _s(f.get('dal'), 5), _s(f.get('al'), 5)
            if re.fullmatch(r'[0-2]\d:[0-5]\d', dal) and re.fullmatch(r'[0-2]\d:[0-5]\d', al) and dal <= al:
                fasce.append({'dal': dal, 'al': al})
        if fasce:
            cfg['fasce'] = fasce
        for k in ('passo_minuti', 'preavviso_minimo_minuti', 'preavviso_modifica_minuti'):
            try:
                v = int(d.get(k))
                if v >= (5 if k == 'passo_minuti' else 0):
                    cfg[k] = v
            except (TypeError, ValueError):
                pass
    except Exception as e:
        print(f'Lettura impostazioni/navetta non riuscita: {e}')
    return cfg


def _contenuti(db):
    """Testi e foto personalizzati dall'Hub. Foto = data URL (JPEG ridotto)
    salvate in `impostazioni/area_ospite_foto_<servizio>`."""
    out = {'testi': {}, 'foto': {}}
    try:
        snap = db.collection('impostazioni').document('area_ospite').get()
        d = snap.to_dict() or {} if snap.exists else {}
        for k in ('animazione_titolo', 'animazione_testo', 'info_testo', 'assistenza_testo',
                  'assistenza_telefono', 'navetta_testo'):
            out['testi'][k] = _s(d.get(k), 4000)
    except Exception as e:
        print(f'Lettura impostazioni/area_ospite non riuscita: {e}')
    for k in SERVIZI_FOTO + ('animazione_programma',):
        try:
            snap = db.collection('impostazioni').document(f'area_ospite_foto_{k}').get()
            url = _s((snap.to_dict() or {}).get('data_url'), 900000) if snap.exists else ''
            if url.startswith('data:image/'):
                out['foto'][k] = url
        except Exception as e:
            print(f'Lettura foto {k} non riuscita: {e}')
    return out


def _nome_proprio(p):
    """Nome di battesimo del capofamiglia. Preferisce l'anagrafica ospiti
    (campi nome/cognome separati); altrimenti la prima parola di `nome`."""
    try:
        for o in (p.get('ospiti') or [])[:1]:
            n = _s((o or {}).get('nome'))
            if n:
                return n.split()[0].capitalize()
    except Exception:
        pass
    parole = _s(p.get('nome')).split()
    return parole[0].capitalize() if parole else ''


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
            {'id': d.id, 'nome': _s((d.to_dict() or {}).get('nome')) or d.id,
             'foto': _s((d.to_dict() or {}).get('foto'), 300000)}
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


def _navetta_corse_cliente(db, pren_id):
    """Tutte le richieste navetta di questo ospite ancora presenti (oggi e
    precedenti: la pulizia periodica elimina quelle chiuse piu' vecchie di N
    giorni). L'ospite non ha accesso diretto a Firestore, le vede solo
    tramite questa azione. Ordinate: prima oggi per orario, poi i giorni
    precedenti dal piu' recente."""
    try:
        q = db.collection('navetta_prenotazioni').where('prenId', '==', pren_id)
        out = []
        for d in q.stream():
            x = d.to_dict() or {}
            out.append({
                'id': d.id,
                'data': _s(x.get('data'), 10),
                'orario': _s(x.get('orario')),
                'stato': _s(x.get('stato')) or 'in_attesa',
                'autista_nome': _s(x.get('autista_nome')),
                'orario_precedente': _s(x.get('orario_precedente')),
            })
        oggi = _oggi_iso()
        out.sort(key=lambda c: (c['data'] != oggi, '' if c['data'] == oggi else _inverti(c['data']), c['orario'] if c['data'] == oggi else _inverti(c['orario'])))
        return out
    except Exception as e:
        print(f'Lettura navetta_prenotazioni cliente non riuscita: {e}')
        return []


def _inverti(testo):
    """Chiave di ordinamento decrescente per stringhe 'AAAA-MM-GG' / 'HH:MM'
    (cifre complementate a 9, cosi' si ordina con sort crescente)."""
    return ''.join(chr(ord('0') + 9 - int(ch)) if ch.isdigit() else ch for ch in (testo or ''))


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

def _slot_validi(cfg):
    """Elenco 'HH:MM' di tutte le fasce, passo configurato (bordo incluso)."""
    out = []
    for f in cfg['fasce']:
        h0, m0 = map(int, f['dal'].split(':'))
        h1, m1 = map(int, f['al'].split(':'))
        t = h0 * 60 + m0
        tf = h1 * 60 + m1
        while t <= tf:
            out.append(f'{t // 60:02d}:{t % 60:02d}')
            t += cfg['passo_minuti']
    return out


def _minuti_da_ora(orario):
    """Minuti tra adesso (ora di Roma) e l'orario 'HH:MM' passato, oggi."""
    h, m = map(int, orario.split(':'))
    ora = datetime.now(TZ_ROMA)
    target = ora.replace(hour=h, minute=m, second=0, microsecond=0)
    return (target - ora).total_seconds() / 60


def _orario_valido(orario, cfg):
    if not bool(re.fullmatch(r'[0-2]\d:[0-5]\d', orario or '')) or orario not in _slot_validi(cfg):
        return False
    return _minuti_da_ora(orario) >= cfg['preavviso_minimo_minuti']


def _norm_nome(v):
    return re.sub(r'\s+', ' ', (v or '').strip().lower())


def _norm_tel(v):
    cifre = re.sub(r'\D', '', v or '')
    return cifre[-9:] if len(cifre) >= 7 else ''


def _corsa_attiva_duplicata(db, pren_id, orario, nome='', telefono='', escludi_id=None):
    """True se la stessa persona ha gia' una corsa ancora attiva allo stesso
    orario oggi. La persona si riconosce dalla prenotazione, dal telefono o dal
    nome: nella realta' una stessa persona non puo' essere in due corse alla
    stessa ora, nemmeno se qualcuno la inserisce a nome di un'altra
    prenotazione dello stesso gruppo."""
    n, t = _norm_nome(nome), _norm_tel(telefono)
    q = db.collection('navetta_prenotazioni').where('data', '==', _oggi_iso())
    for d in q.stream():
        x = d.to_dict() or {}
        if d.id == escludi_id or x.get('orario') != orario or x.get('stato') not in ('in_attesa', 'accettata'):
            continue
        if x.get('prenId') == pren_id:
            return True
        if t and _norm_tel(x.get('telefono')) == t:
            return True
        if n and _norm_nome(x.get('nome')) == n:
            return True
    return False


# ── azioni ─────────────────────────────────────────────────────────────────

def _azione_carica(db, origin, data):
    pren_ref, p = _risolvi_token(db, data.get('token'))
    if not p:
        return _json(origin, {'ok': False, 'errore': 'link_non_valido'}, 404)
    cfg = _cfg_navetta(db)

    return _json(origin, {
        'ok': True,
        'prenotazione': {
            'nome':          _s(p.get('nome')),
            'nome_proprio':  _nome_proprio(p),
            'telefono':      _s(p.get('tel')),
            'alloggio_nome': _s(p.get('alloggio_nome')),
            'checkin':       _s(p.get('checkin')),
            'checkout':      _s(p.get('checkout')),
        },
        'spiaggia': _spiaggia_assegnata(db, pren_ref.id),
        'spiagge': _spiagge_disponibili(db),
        'autisti': _autisti_elenco(db),
        'ristorazione': _ristorazione_disponibile(db, pren_ref.id),
        'navetta_corse': _navetta_corse_cliente(db, pren_ref.id),
        'oggi': _oggi_iso(),
        'fasce': cfg['fasce'],
        'passo_minuti': cfg['passo_minuti'],
        'preavviso_minimo_minuti': cfg['preavviso_minimo_minuti'],
        'preavviso_modifica_minuti': cfg['preavviso_modifica_minuti'],
    })


def _azione_contenuti(db, origin, data):
    pren_ref, p = _risolvi_token(db, data.get('token'))
    if not p:
        return _json(origin, {'ok': False, 'errore': 'link_non_valido'}, 404)
    return _json(origin, {'ok': True, **_contenuti(db)})


def _azione_navetta_stato(db, origin, data):
    pren_ref, p = _risolvi_token(db, data.get('token'))
    if not p:
        return _json(origin, {'ok': False, 'errore': 'link_non_valido'}, 404)
    return _json(origin, {'ok': True, 'navetta_corse': _navetta_corse_cliente(db, pren_ref.id), 'oggi': _oggi_iso()})


def _azione_navetta_prenota(db, origin, data):
    pren_ref, p = _risolvi_token(db, data.get('token'))
    if not p:
        return _json(origin, {'ok': False, 'errore': 'link_non_valido'}, 404)
    cfg = _cfg_navetta(db)

    orario = _s(data.get('orario'), 5)
    if not _orario_valido(orario, cfg):
        return _json(origin, {'ok': False, 'errore': 'orario_non_valido'}, 400)

    nome = _s(data.get('nome')) or _s(p.get('nome'))
    telefono = _s(data.get('telefono')) or _s(p.get('tel'))
    if _corsa_attiva_duplicata(db, pren_ref.id, orario, nome, telefono):
        return _json(origin, {'ok': False, 'errore': 'corsa_duplicata'}, 409)
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
    # Id deterministico (prenotazione + giorno + orario) e create() atomica:
    # due richieste identiche inviate insieme (doppio tap, due dispositivi)
    # non possono generare due corse.
    col = db.collection('navetta_prenotazioni')
    ref = col.document(f"{pren_ref.id}_{_oggi_iso()}_{orario.replace(':', '')}")
    try:
        ref.create(doc)
    except AlreadyExists:
        esistente = (ref.get().to_dict() or {})
        if esistente.get('orario') == orario and esistente.get('stato') in ('in_attesa', 'accettata'):
            return _json(origin, {'ok': False, 'errore': 'corsa_duplicata'}, 409)
        # id occupato da una corsa chiusa o spostata: nuovo documento a id libero
        ref = col.document()
        ref.set(doc)
    return _json(origin, {'ok': True, 'id': ref.id})


def _azione_navetta_modifica_orario(db, origin, data):
    pren_ref, p = _risolvi_token(db, data.get('token'))
    if not p:
        return _json(origin, {'ok': False, 'errore': 'link_non_valido'}, 404)
    cfg = _cfg_navetta(db)

    ref = db.collection('navetta_prenotazioni').document(_s(data.get('id'), 60) or '_')
    snap = ref.get()
    c = snap.to_dict() if snap.exists else None
    if not c or c.get('prenId') != pren_ref.id or c.get('data') != _oggi_iso():
        return _json(origin, {'ok': False, 'errore': 'corsa_non_trovata'}, 404)
    if c.get('stato') not in ('in_attesa', 'accettata'):
        return _json(origin, {'ok': False, 'errore': 'corsa_non_modificabile'}, 409)
    # Si puo' spostare solo finche' mancano abbastanza minuti alla corsa attuale.
    if _minuti_da_ora(c.get('orario') or '00:00') < cfg['preavviso_modifica_minuti']:
        return _json(origin, {'ok': False, 'errore': 'troppo_tardi'}, 409)

    orario = _s(data.get('orario'), 5)
    if not _orario_valido(orario, cfg):
        return _json(origin, {'ok': False, 'errore': 'orario_non_valido'}, 400)
    if orario == c.get('orario'):
        return _json(origin, {'ok': True, 'id': snap.id})
    if _corsa_attiva_duplicata(db, pren_ref.id, orario, c.get('nome'), c.get('telefono'), escludi_id=snap.id):
        return _json(origin, {'ok': False, 'errore': 'corsa_duplicata'}, 409)

    ref.update({
        'orario': orario,
        'orario_precedente': c.get('orario') or '',
        'orario_modificato_il': _now_iso(),
        'aggiornato_il': _now_iso(),
    })
    return _json(origin, {'ok': True, 'id': snap.id})


AZIONI = {
    'carica':                  _azione_carica,
    'contenuti':               _azione_contenuti,
    'navetta_stato':           _azione_navetta_stato,
    'navetta_prenota':         _azione_navetta_prenota,
    'navetta_modifica_orario': _azione_navetta_modifica_orario,
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
