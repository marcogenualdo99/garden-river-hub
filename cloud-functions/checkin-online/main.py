"""Check-in online ospiti — Garden Hub.

Endpoint HTTP pubblico usato dalla pagina https://gardenhub.it/checkin/?t=<token>.
Il browser dell'ospite NON tocca mai Firestore o Storage: tutto passa da qui
(Admin SDK, che ignora le regole di sicurezza).

Azioni (campo "azione" nel corpo JSON):
  - carica : { token }
        -> riassunto sanificato della prenotazione + testi consenso + schede
           ospite da compilare
  - invia  : { token, ospiti[], consensi{privacy,regolamento}, foto[] }
        -> valida, carica le foto documento su Storage, scrive `ospiti` e
           `checkin_online` sulla prenotazione, avvisa la reception via email

Il collegamento token -> prenotazione avviene SOLO qui, tramite la collezione
`checkin_links/{token}` (che le regole Firestore negano in lettura a tutti i
client — l'hub può solo crearla).

Variabili d'ambiente attese (impostate in Console Cloud Run / Secret Manager):
  SMTP_HOST      (default smtps.aruba.it)
  SMTP_PORT      (default 465)
  SMTP_USER      casella Aruba
  SMTP_PASS      password casella
  MAIL_FROM      mittente (default = SMTP_USER)
  MAIL_RECEPTION destinatario della notifica (se assente, l'email è saltata)
  STORAGE_BUCKET (default garden-river-conti-febed.firebasestorage.app)
"""

import base64
import datetime
import hmac
import json
import os
import re
import secrets
import smtplib
import time
import uuid
from email.message import EmailMessage
from urllib.parse import quote

import firebase_admin
from firebase_admin import firestore, storage
import functions_framework

if not firebase_admin._apps:
    firebase_admin.initialize_app()

ALLOWED_ORIGINS = {'https://gardenhub.it', 'https://www.gardenhub.it'}
SITE_URL        = 'https://gardenhub.it'
DEFAULT_BUCKET  = 'garden-river-conti-febed.firebasestorage.app'

MAX_OSPITI     = 20
MAX_FOTO       = 8
MAX_FOTO_BYTES = 5 * 1024 * 1024        # per foto, dopo il resize lato client

CAMPI_OSPITE = (
    'cognome', 'nome', 'sesso', 'data_nascita', 'comune_nascita',
    'provincia_nascita', 'stato_nascita', 'cittadinanza',
    'esenzione_tassa_soggiorno',
)
CAMPI_DOC = ('tipo_documento', 'numero_documento', 'luogo_rilascio_documento')
ESENZIONI_VALIDE = {'', 'eta_minore', 'eta_over', 'disabilita'}

PRIVACY_DEFAULT = (
    "Autorizzo Garden River al trattamento dei dati personali e dei documenti "
    "di identità qui forniti per gli adempimenti di legge sulla comunicazione "
    "degli alloggiati alla Questura (art. 109 TULPS) e per la gestione del "
    "soggiorno, ai sensi del Regolamento UE 2016/679."
)
REGOLAMENTO_DEFAULT = (
    "Dichiaro di aver preso visione e di accettare il regolamento della "
    "struttura."
)


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


def _s(v):
    return str(v).strip() if v is not None else ''


def _fmt_data_it(iso):
    iso = _s(iso)
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', iso):
        return iso
    y, m, d = iso.split('-')
    return f'{d}/{m}/{y}'


# ── token / prenotazione ───────────────────────────────────────────────────

def _token_valido(token):
    return bool(re.fullmatch(r'[a-f0-9]{16,64}', token or ''))


def _risolvi_token(db, token):
    """Ritorna (pren_ref, pren_dict, link_ref) oppure (None, None, None)."""
    if not _token_valido(token):
        return None, None, None
    link_ref = db.collection('checkin_links').document(token)
    snap = link_ref.get()
    if not snap.exists:
        return None, None, None
    d = snap.to_dict() or {}
    scade_il = d.get('scade_il') or 0
    if scade_il and scade_il < _now_ms():
        try:
            link_ref.delete()          # link scaduto: pulizia opportunistica
        except Exception:
            pass
        return None, None, None
    pren_id = d.get('prenId')
    if not pren_id:
        return None, None, None
    pren_ref = db.collection('prenotazioni').document(pren_id)
    pren = pren_ref.get()
    if not pren.exists:
        return None, None, None
    return pren_ref, (pren.to_dict() or {}), link_ref


def _oggi_iso():
    return time.strftime('%Y-%m-%d', time.gmtime())


def _iso_piu_giorni(iso, n):
    d = datetime.date.fromisoformat(iso) + datetime.timedelta(days=n)
    return d.isoformat()


def _scadenza_link_ms(checkout_iso):
    """checkout + 3 giorni in epoch ms — stesso valore che scrive il client."""
    try:
        d = datetime.date.fromisoformat(checkout_iso)
        dt = datetime.datetime(d.year, d.month, d.day, 12, tzinfo=datetime.timezone.utc)
        return int((dt + datetime.timedelta(days=3)).timestamp() * 1000)
    except Exception:
        return _now_ms() + 30 * 24 * 3600 * 1000


def _assicura_token(db, pren_ref, p):
    """Token della prenotazione: lo riusa se c'è, altrimenti lo crea insieme al
    doc checkin_links/{token}. Muta anche p['checkin_token']."""
    tok = _s(p.get('checkin_token'))
    if _token_valido(tok):
        return tok
    tok = secrets.token_hex(16)
    db.collection('checkin_links').document(tok).set({
        'prenId': pren_ref.id,
        'creato_il': _now_iso(),
        'scade_il': _scadenza_link_ms(_s(p.get('checkout'))),
    })
    pren_ref.update({'checkin_token': tok})
    p['checkin_token'] = tok
    return tok


def _persone_attese(p):
    fasce = ('bambini_0_2', 'bambini_3_4', 'bambini_5_9', 'bambini_10_17')
    tot = (p.get('adulti') or 0) + sum(p.get(k) or 0 for k in fasce)
    if not tot:
        tot = (p.get('adulti') or 0) + (p.get('bambini') or 0)
    return max(int(tot), 1)


def _ospite_pubblico(o):
    if not isinstance(o, dict):
        return {}
    fuori = {'notti_tassa_soggiorno'}
    return {k: v for k, v in o.items() if k not in fuori}


def _riassunto(p):
    co = (p.get('checkin_online') or {})
    return {
        'nome':           _s(p.get('nome')),
        'alloggio_nome':  _s(p.get('alloggio_nome')),
        'checkin':        _s(p.get('checkin')),
        'checkout':       _s(p.get('checkout')),
        'persone_attese': _persone_attese(p),
        'ospiti':         [_ospite_pubblico(o) for o in (p.get('ospiti') or [])],
        'stato':          'ricevuto' if co.get('stato') == 'ricevuto' else 'nuovo',
    }


# ── validazione ospiti ─────────────────────────────────────────────────────

def _pulisci_e_valida_ospiti(ospiti_in):
    ospiti, errori = [], []
    for i, raw in enumerate(ospiti_in):
        chi = 'Capofamiglia' if i == 0 else f'Familiare {i}'
        if not isinstance(raw, dict):
            errori.append(f'{chi}: dati non validi')
            continue
        o = {k: _s(raw.get(k)) for k in CAMPI_OSPITE}
        o['ruolo'] = 'capo' if i == 0 else 'familiare'
        o['presenza'] = 'in_arrivo'
        o['sesso'] = 'F' if o['sesso'] == 'F' else 'M'
        o['provincia_nascita'] = o['provincia_nascita'].upper()[:2]
        if o['esenzione_tassa_soggiorno'] not in ESENZIONI_VALIDE:
            o['esenzione_tassa_soggiorno'] = ''

        for campo, etichetta in (
            ('cognome', 'cognome'), ('nome', 'nome'),
            ('data_nascita', 'data di nascita'),
            ('comune_nascita', 'luogo di nascita'),
            ('stato_nascita', 'stato di nascita'),
            ('cittadinanza', 'cittadinanza'),
        ):
            if not o[campo]:
                errori.append(f'{chi}: {etichetta} mancante')
        if o['data_nascita'] and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', o['data_nascita']):
            errori.append(f'{chi}: data di nascita non valida')

        if i == 0:
            for campo in CAMPI_DOC:
                o[campo] = _s(raw.get(campo))
            if not o['tipo_documento']:
                errori.append(f'{chi}: tipo documento mancante')
            if not o['numero_documento']:
                errori.append(f'{chi}: numero documento mancante')
            if not o['luogo_rilascio_documento']:
                errori.append(f'{chi}: luogo di rilascio documento mancante')

        ospiti.append(o)
    return ospiti, errori


# ── foto documento su Storage ──────────────────────────────────────────────

_DATA_URL_RE = re.compile(r'^data:image/(jpeg|jpg|png|webp);base64,(.+)$', re.DOTALL)


def _carica_foto(pren_id, foto_in):
    bucket = storage.bucket(os.environ.get('STORAGE_BUCKET', DEFAULT_BUCKET))
    out = []
    ts = int(time.time())
    for idx, f in enumerate(foto_in):
        if not isinstance(f, dict):
            raise ValueError('foto_non_valide')
        m = _DATA_URL_RE.match(_s(f.get('data_url')))
        if not m:
            raise ValueError('foto_formato')
        try:
            raw = base64.b64decode(m.group(2))
        except Exception:
            raise ValueError('foto_formato')
        if not raw or len(raw) > MAX_FOTO_BYTES:
            raise ValueError('foto_troppo_grande')

        mime = 'jpeg' if m.group(1) in ('jpeg', 'jpg') else m.group(1)
        ext = 'jpg' if mime == 'jpeg' else mime
        ospite_idx = max(0, int(f.get('ospite_idx') or 0))
        tipo = re.sub(r'[^a-z0-9_-]', '', _s(f.get('tipo')).lower())[:20] or 'doc'
        path = f'checkin/{pren_id}/{ospite_idx}-{tipo}-{ts}-{idx}.{ext}'

        download_token = str(uuid.uuid4())
        blob = bucket.blob(path)
        blob.metadata = {'firebaseStorageDownloadTokens': download_token}
        blob.upload_from_string(raw, content_type=f'image/{mime}')
        url = (
            f'https://firebasestorage.googleapis.com/v0/b/{bucket.name}/o/'
            f'{quote(path, safe="")}?alt=media&token={download_token}'
        )
        out.append({'ospite_idx': ospite_idx, 'tipo': tipo, 'path': path, 'url': url})
    return out


# ── email ──────────────────────────────────────────────────────────────────

def _invia_email(dest, oggetto, corpo_txt):
    host = os.environ.get('SMTP_HOST', 'smtps.aruba.it')
    port = int(os.environ.get('SMTP_PORT', '465'))
    user = os.environ.get('SMTP_USER', '')
    pw   = os.environ.get('SMTP_PASS', '')
    mittente = os.environ.get('MAIL_FROM', user)
    if not (user and pw and mittente):
        raise RuntimeError('SMTP non configurato (SMTP_USER / SMTP_PASS / MAIL_FROM)')

    msg = EmailMessage()
    msg['Subject'] = oggetto
    msg['From'] = mittente
    msg['To'] = dest
    msg.set_content(corpo_txt)

    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=20) as srv:
            srv.login(user, pw)
            srv.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as srv:
            srv.starttls()
            srv.login(user, pw)
            srv.send_message(msg)


def _notifica_reception(p, ospiti, pren_id):
    dest = os.environ.get('MAIL_RECEPTION', '')
    if not dest:
        print('MAIL_RECEPTION non configurato: notifica email saltata')
        return
    nome     = _s(p.get('nome')) or 'Ospite'
    alloggio = _s(p.get('alloggio_nome')) or '—'
    ci, co   = _fmt_data_it(p.get('checkin')), _fmt_data_it(p.get('checkout'))
    righe = '\n'.join(
        f"  {i+1}. {o.get('cognome','')} {o.get('nome','')}"
        f" · {_fmt_data_it(o.get('data_nascita'))}"
        f"{'  (documento allegato)' if i == 0 else ''}"
        for i, o in enumerate(ospiti)
    )
    oggetto = f'Check-in online ricevuto — {nome} · {alloggio}'
    corpo = (
        f"{nome} ha completato il check-in online.\n\n"
        f"Alloggio:  {alloggio}\n"
        f"Soggiorno: {ci} -> {co}\n"
        f"Persone:   {len(ospiti)}\n\n"
        f"{righe}\n\n"
        f"Apri il Calendario e cerca la prenotazione di \"{nome}\": nella scheda "
        f"\"Dettaglio ospiti\" trovi i dati e le foto del documento da verificare.\n"
        f"{SITE_URL}/calendario/\n"
    )
    try:
        _invia_email(dest, oggetto, corpo)
    except Exception as e:
        print(f'Invio email reception fallito: {e}')


# ── invito al cliente ──────────────────────────────────────────────────────

def _costruisci_invito(p, link):
    nome = (_s(p.get('nome')).split() or ['Gentile ospite'])[0]
    alloggio = _s(p.get('alloggio_nome')) or 'il tuo alloggio'
    ci, co = _fmt_data_it(p.get('checkin')), _fmt_data_it(p.get('checkout'))
    oggetto = 'Check-in online — Garden River'
    corpo = (
        f"Gentile {nome},\n\n"
        f"per velocizzare l'arrivo a Garden River la invitiamo a compilare il "
        f"check-in online da questo link:\n{link}\n\n"
        f"Servono i dati di tutte le persone che soggiorneranno e la foto di un "
        f"documento d'identità di chi prenota. Bastano pochi minuti e all'arrivo "
        f"eviterà la compilazione al banco.\n\n"
        f"Soggiorno: {alloggio}, {ci} -> {co}\n\n"
        f"A presto,\nGarden River\n"
    )
    return oggetto, corpo


def _invia_invito(db, pren_ref, p):
    """Manda l'email di invito al check-in all'indirizzo della prenotazione.
    Ritorna uno di: 'ok' | 'no_email' | 'gia_inviato' | 'gia_fatto' | 'errore'.
    Il secondo valore è l'email (o il testo errore)."""
    email = _s(p.get('email'))
    if not email or '@' not in email:
        return 'no_email', None
    if _s((p.get('checkin_invito') or {}).get('inviato_il')):
        return 'gia_inviato', None
    if p.get('checkin_fatto') or (p.get('checkin_online') or {}).get('stato') == 'ricevuto':
        return 'gia_fatto', None

    tok = _assicura_token(db, pren_ref, p)
    oggetto, corpo = _costruisci_invito(p, f'{SITE_URL}/checkin/?t={tok}')
    try:
        _invia_email(email, oggetto, corpo)
    except Exception as e:
        return 'errore', str(e)
    pren_ref.update({'checkin_invito': {'inviato_il': _now_iso(), 'a': email}})
    return 'ok', email


# ── azioni ─────────────────────────────────────────────────────────────────

def _azione_test_email(db, origin, data):
    """Invia un'email di prova a MAIL_RECEPTION, per verificare le credenziali
    SMTP senza dover fare un check-in vero. Destinatario fisso (l'indirizzo
    della reception), quindi non è sfruttabile per spam verso terzi."""
    dest = os.environ.get('MAIL_RECEPTION', '')
    if not dest:
        return _json(origin, {'ok': False, 'errore': 'MAIL_RECEPTION non configurato'}, 400)
    try:
        _invia_email(
            dest,
            'Test check-in online — Garden River',
            "Se leggi questa email, l'invio dalla funzione checkin-online verso "
            "la reception funziona correttamente.\n\nPuoi ignorare questo messaggio.\n",
        )
    except Exception as e:
        return _json(origin, {'ok': False, 'errore': f'invio fallito: {e}'}, 500)
    return _json(origin, {'ok': True, 'inviata_a': dest})


def _azione_carica(db, origin, data):
    _, p, _ = _risolvi_token(db, data.get('token'))
    if not p:
        return _json(origin, {'ok': False, 'errore': 'link_non_valido'}, 404)

    imp = {}
    try:
        snap = db.collection('impostazioni').document('calendario').get()
        if snap.exists:
            imp = snap.to_dict() or {}
    except Exception as e:
        print(f'impostazioni/calendario non lette: {e}')

    return _json(origin, {
        'ok': True,
        'prenotazione': _riassunto(p),
        'testo_privacy':     _s(imp.get('testoPrivacyCheckin')) or PRIVACY_DEFAULT,
        'testo_regolamento': _s(imp.get('testoRegolamentoCheckin')) or REGOLAMENTO_DEFAULT,
        'esenzioni': [
            {'v': '',            'label': 'Nessuna (paga la tassa di soggiorno)'},
            {'v': 'eta_minore',  'label': 'Minore di 13 anni'},
            {'v': 'eta_over',    'label': '70 anni o più'},
            {'v': 'disabilita',  'label': 'Disabile / accompagnatore'},
        ],
    })


def _azione_invia(db, origin, data):
    pren_ref, p, _ = _risolvi_token(db, data.get('token'))
    if not p:
        return _json(origin, {'ok': False, 'errore': 'link_non_valido'}, 404)

    consensi = data.get('consensi') or {}
    if consensi.get('privacy') is not True or consensi.get('regolamento') is not True:
        return _json(origin, {'ok': False, 'errore': 'consensi_mancanti'}, 400)

    ospiti_in = data.get('ospiti')
    if not isinstance(ospiti_in, list) or not (1 <= len(ospiti_in) <= MAX_OSPITI):
        return _json(origin, {'ok': False, 'errore': 'ospiti_non_validi'}, 400)

    attese = _persone_attese(p)
    if len(ospiti_in) > attese:
        return _json(origin, {'ok': False, 'errore': 'troppi_ospiti', 'attese': attese}, 400)

    ospiti, errori = _pulisci_e_valida_ospiti(ospiti_in)
    if errori:
        return _json(origin, {'ok': False, 'errore': 'dati_incompleti', 'dettagli': errori}, 400)

    foto_in = data.get('foto') or []
    if not isinstance(foto_in, list) or len(foto_in) > MAX_FOTO:
        return _json(origin, {'ok': False, 'errore': 'foto_non_valide'}, 400)
    try:
        foto_meta = _carica_foto(pren_ref.id, foto_in)
    except ValueError as e:
        return _json(origin, {'ok': False, 'errore': str(e)}, 400)

    # Conserva le notti già calcolate per la tassa di soggiorno (le riusa il
    # ricalcolo cumulativo delle altre prenotazioni) allineando per indice.
    vecchi = p.get('ospiti') or []
    for i, o in enumerate(ospiti):
        if i < len(vecchi) and isinstance(vecchi[i], dict):
            n = vecchi[i].get('notti_tassa_soggiorno')
            if n is not None:
                o['notti_tassa_soggiorno'] = n

    pren_ref.update({
        'ospiti': ospiti,
        'checkin_online': {
            'stato': 'ricevuto',
            'ricevuto_il': _now_iso(),
            'consensi': {'privacy': True, 'regolamento': True},
            'foto': foto_meta,
        },
    })

    try:
        pren_ref.collection('log').add({
            'timestamp': _now_iso(),
            'operatore': 'Check-in online',
            'voci': [f'Dati e documento inviati dall\'ospite ({len(ospiti)} '
                     f'{"persona" if len(ospiti) == 1 else "persone"})'],
        })
    except Exception as e:
        print(f'log check-in non scritto: {e}')

    _notifica_reception(p, ospiti, pren_ref.id)
    return _json(origin, {'ok': True})


def _azione_invito(db, origin, data):
    """Invio manuale/on-demand dall'hub. Body { prenId, forza? }."""
    pren_id = _s(data.get('prenId'))
    if not pren_id:
        return _json(origin, {'ok': False, 'errore': 'prenId_mancante'}, 400)
    pren_ref = db.collection('prenotazioni').document(pren_id)
    snap = pren_ref.get()
    if not snap.exists:
        return _json(origin, {'ok': False, 'errore': 'prenotazione_inesistente'}, 404)
    p = snap.to_dict() or {}
    if data.get('forza'):
        p.pop('checkin_invito', None)      # consente il rinvio
    esito, dett = _invia_invito(db, pren_ref, p)
    if esito == 'ok':
        return _json(origin, {'ok': True, 'inviata_a': dett})
    if esito == 'errore':
        return _json(origin, {'ok': False, 'errore': f'invio fallito: {dett}'}, 500)
    return _json(origin, {'ok': False, 'errore': esito}, 409 if esito != 'no_email' else 400)


def _azione_cron(db, origin, data):
    """Chiamata da Cloud Scheduler una volta al giorno. Manda l'invito a tutte
    le prenotazioni in arrivo entro INVITO_GIORNI_PRIMA giorni che hanno
    un'email e non l'hanno ancora ricevuto. Con { dry_run: true } elenca
    soltanto, senza spedire."""
    atteso = os.environ.get('CRON_TOKEN', '')
    if atteso and not hmac.compare_digest(_s(data.get('_cron_token')), atteso):
        return _json(origin, {'ok': False, 'errore': 'token_non_valido'}, 403)

    try:
        giorni = max(0, int(os.environ.get('INVITO_GIORNI_PRIMA', '5')))
    except ValueError:
        giorni = 5
    dry = bool(data.get('dry_run'))
    oggi = _oggi_iso()
    limite = _iso_piu_giorni(oggi, giorni)

    q = (db.collection('prenotazioni')
           .where('checkin', '>=', oggi)
           .where('checkin', '<=', limite))

    inviati = saltati = errori = 0
    anteprima = []
    for snap in q.stream():
        p = snap.to_dict() or {}
        email = _s(p.get('email'))
        if (not email or '@' not in email
                or _s((p.get('checkin_invito') or {}).get('inviato_il'))
                or p.get('checkin_fatto')
                or (p.get('checkin_online') or {}).get('stato') == 'ricevuto'):
            saltati += 1
            continue
        if dry:
            anteprima.append({'prenId': snap.id, 'nome': _s(p.get('nome')),
                              'email': email, 'checkin': _s(p.get('checkin'))})
            continue
        esito, _dett = _invia_invito(db, snap.reference, p)
        if esito == 'ok':
            inviati += 1
        elif esito == 'errore':
            errori += 1
            print(f'invito fallito per {snap.id}: {_dett}')
        else:
            saltati += 1

    res = {'ok': True, 'giorni': giorni, 'inviati': inviati,
           'saltati': saltati, 'errori': errori}
    if dry:
        res['anteprima'] = anteprima
    return _json(origin, res)


AZIONI = {
    'carica': _azione_carica,
    'invia':  _azione_invia,
    'invito': _azione_invito,
    'cron':   _azione_cron,
    'test_email': _azione_test_email,
}


@functions_framework.http
def checkin_online(request):
    origin = request.headers.get('Origin', '')

    if request.method == 'OPTIONS':
        return ('', 204, _cors_headers(origin))
    if request.method != 'POST':
        return _json(origin, {'ok': False, 'errore': 'metodo_non_permesso'}, 405)

    data = request.get_json(silent=True) or {}
    # Cloud Scheduler può passare il token del cron come header invece che nel corpo.
    if not data.get('_cron_token'):
        data['_cron_token'] = request.headers.get('X-Cron-Token', '')
    handler = AZIONI.get(data.get('azione'))
    if not handler:
        return _json(origin, {'ok': False, 'errore': 'azione_non_valida'}, 400)

    try:
        return handler(firestore.client(), origin, data)
    except Exception as e:
        print(f'Errore azione {data.get("azione")}: {e}')
        return _json(origin, {'ok': False, 'errore': 'errore_interno'}, 500)
