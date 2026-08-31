"""Verifica dei PIN operatore lato server.

Motivazione: la collezione `operatori` è leggibile da qualunque client
autenticato (anche in anonimo). Finché il PIN stava lì in chiaro, chiunque
poteva scaricarlo. Ora nel database resta solo un hash salato in
`operatori_pin/{nome}`, collezione che le regole Firestore negano a TUTTI i
client: solo questa funzione (Admin SDK) la legge/scrive.

Endpoint HTTP unico, azione nel corpo JSON:
  - verifica : { nome, pin }                -> { ok, ruolo } | { ok:false, errore }
  - imposta  : { nome, pin }                -> primo PIN (come "Imposta PIN per X")
  - reset    : { nome, adminNome, adminPin }-> un admin azzera il PIN di qualcuno
  - migra    : { token[, pulisci] }         -> una tantum, dai PIN in chiaro agli hash
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

import firebase_admin
from firebase_admin import firestore
import functions_framework

if not firebase_admin._apps:
    firebase_admin.initialize_app()

ALLOWED_ORIGINS = {'https://gardenhub.it', 'https://www.gardenhub.it'}

PBKDF2_ITER   = 200_000
SALT_BYTES    = 16
MAX_TENTATIVI = 5
BLOCCO_MINUTI = 15
PIN_MIN_LEN   = 4
PIN_MAX_LEN   = 12


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


def _hash_pin(pin, salt_b64, iters=PBKDF2_ITER):
    salt = base64.b64decode(salt_b64)
    dk = hashlib.pbkdf2_hmac('sha256', pin.encode('utf-8'), salt, int(iters))
    return base64.b64encode(dk).decode('ascii')


def _nuovo_record(pin):
    salt_b64 = base64.b64encode(secrets.token_bytes(SALT_BYTES)).decode('ascii')
    return {
        'hash': _hash_pin(pin, salt_b64),
        'salt': salt_b64,
        'iter': PBKDF2_ITER,
        'tentativi': 0,
        'bloccato_fino': 0,
        'updated_at': _now_ms(),
    }


def _pin_valido(pin):
    return isinstance(pin, str) and pin.isdigit() and PIN_MIN_LEN <= len(pin) <= PIN_MAX_LEN


def _nome_valido(nome):
    # I nomi arrivano da un <select> (operatori reali), ma questo è un endpoint
    # pubblico: un ID non valido per Firestore ('/', '__x__', ecc.) altrimenti
    # farebbe sollevare un'eccezione invece di un errore pulito.
    return (
        isinstance(nome, str)
        and 0 < len(nome) <= 128
        and '/' not in nome
        and nome not in ('.', '..')
        and not (nome.startswith('__') and nome.endswith('__'))
    )


def _ruolo(db, nome):
    snap = db.collection('operatori').document(nome).get()
    if not snap.exists:
        return 'operatore'
    return (snap.to_dict() or {}).get('ruolo', 'operatore')


def _verifica_pin(db, nome, pin):
    """Ritorna (esito, dettaglio) con esito in {'ok','errato','nessun_pin','bloccato'}."""
    ref = db.collection('operatori_pin').document(nome)
    snap = ref.get()
    if not snap.exists:
        return 'nessun_pin', None
    d = snap.to_dict() or {}

    bloccato_fino = d.get('bloccato_fino') or 0
    if bloccato_fino > _now_ms():
        minuti = max(1, round((bloccato_fino - _now_ms()) / 60000))
        return 'bloccato', minuti

    atteso    = d.get('hash') or ''
    calcolato = _hash_pin(pin, d.get('salt') or '', d.get('iter') or PBKDF2_ITER)
    if atteso and hmac.compare_digest(atteso, calcolato):
        ref.update({'tentativi': 0, 'bloccato_fino': 0})
        return 'ok', None

    tentativi = (d.get('tentativi') or 0) + 1
    if tentativi >= MAX_TENTATIVI:
        ref.update({'tentativi': 0, 'bloccato_fino': _now_ms() + BLOCCO_MINUTI * 60000})
        return 'bloccato', BLOCCO_MINUTI
    ref.update({'tentativi': tentativi})
    return 'errato', None


# ── azioni ─────────────────────────────────────────────────────────────────

def _azione_verifica(db, origin, data):
    nome = (data.get('nome') or '').strip()
    pin  = data.get('pin') or ''
    if not nome or not pin:
        return _json(origin, {'ok': False, 'errore': 'dati_mancanti'}, 400)
    if not _nome_valido(nome):
        return _json(origin, {'ok': False, 'errore': 'nessun_pin'})
    esito, dettaglio = _verifica_pin(db, nome, pin)
    if esito == 'ok':
        return _json(origin, {'ok': True, 'ruolo': _ruolo(db, nome)})
    if esito == 'bloccato':
        return _json(origin, {'ok': False, 'errore': 'bloccato', 'minuti': dettaglio})
    if esito == 'nessun_pin':
        return _json(origin, {'ok': False, 'errore': 'nessun_pin'})
    return _json(origin, {'ok': False, 'errore': 'pin_errato'})


def _azione_imposta(db, origin, data):
    nome = (data.get('nome') or '').strip()
    pin  = data.get('pin') or ''
    if not nome or not _nome_valido(nome):
        return _json(origin, {'ok': False, 'errore': 'dati_mancanti'}, 400)
    if not _pin_valido(pin):
        return _json(origin, {'ok': False, 'errore': 'pin_non_valido'}, 400)
    if not db.collection('operatori').document(nome).get().exists:
        return _json(origin, {'ok': False, 'errore': 'operatore_sconosciuto'}, 404)
    ref = db.collection('operatori_pin').document(nome)
    if ref.get().exists:
        return _json(origin, {'ok': False, 'errore': 'pin_gia_impostato'}, 409)
    ref.set(_nuovo_record(pin))
    db.collection('operatori').document(nome).update({'haPin': True})
    return _json(origin, {'ok': True, 'ruolo': _ruolo(db, nome)})


def _azione_reset(db, origin, data):
    nome       = (data.get('nome') or '').strip()
    admin_nome = (data.get('adminNome') or '').strip()
    admin_pin  = data.get('adminPin') or ''
    if not nome or not admin_nome or not admin_pin:
        return _json(origin, {'ok': False, 'errore': 'dati_mancanti'}, 400)
    if not _nome_valido(nome) or not _nome_valido(admin_nome):
        return _json(origin, {'ok': False, 'errore': 'dati_mancanti'}, 400)
    if _ruolo(db, admin_nome) != 'admin':
        return _json(origin, {'ok': False, 'errore': 'non_autorizzato'}, 403)
    esito, dettaglio = _verifica_pin(db, admin_nome, admin_pin)
    if esito != 'ok':
        if esito == 'bloccato':
            return _json(origin, {'ok': False, 'errore': 'bloccato', 'minuti': dettaglio})
        return _json(origin, {'ok': False, 'errore': 'pin_admin_errato'}, 403)
    db.collection('operatori_pin').document(nome).delete()
    try:
        db.collection('operatori').document(nome).update({'haPin': False})
    except Exception as e:  # documento operatore inesistente: non è un problema
        print(f'reset: haPin non aggiornato per {nome}: {e}')
    return _json(origin, {'ok': True})


def _azione_migra(db, origin, data):
    atteso = os.environ.get('MIGRA_TOKEN', '')
    if not atteso or not hmac.compare_digest(data.get('token') or '', atteso):
        return _json(origin, {'ok': False, 'errore': 'token_non_valido'}, 403)
    pulisci = bool(data.get('pulisci'))
    migrati, puliti = 0, 0
    for doc in db.collection('operatori').stream():
        d = doc.to_dict() or {}
        pin = d.get('pin')
        ref_pin = db.collection('operatori_pin').document(doc.id)
        esiste_hash = ref_pin.get().exists
        if pin and not esiste_hash:
            ref_pin.set(_nuovo_record(pin))
            esiste_hash = True
            migrati += 1
        update = {'haPin': bool(esiste_hash)}
        if pulisci and 'pin' in d:
            update['pin'] = firestore.DELETE_FIELD
            puliti += 1
        doc.reference.update(update)
    return _json(origin, {'ok': True, 'migrati': migrati, 'puliti': puliti})


AZIONI = {
    'verifica': _azione_verifica,
    'imposta':  _azione_imposta,
    'reset':    _azione_reset,
    'migra':    _azione_migra,
}


@functions_framework.http
def auth_operatori(request):
    origin = request.headers.get('Origin', '')

    if request.method == 'OPTIONS':
        return ('', 204, _cors_headers(origin))
    if request.method != 'POST':
        return _json(origin, {'ok': False, 'errore': 'metodo_non_permesso'}, 405)

    data    = request.get_json(silent=True) or {}
    handler = AZIONI.get(data.get('azione'))
    if not handler:
        return _json(origin, {'ok': False, 'errore': 'azione_non_valida'}, 400)

    try:
        return handler(firestore.client(), origin, data)
    except Exception as e:
        print(f'Errore azione {data.get("azione")}: {e}')
        return _json(origin, {'ok': False, 'errore': 'errore_interno'}, 500)
