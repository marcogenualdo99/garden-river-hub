import time
import json

import firebase_admin
from firebase_admin import firestore, messaging
import functions_framework

if not firebase_admin._apps:
    firebase_admin.initialize_app()

SITE_URL        = 'https://www.gardenhub.it'
ALLOWED_ORIGINS = {'https://gardenhub.it', 'https://www.gardenhub.it'}

EMOJI_STATO = {
    'checkout_ok':     '🧹',
    'da_pulire':       '🧹',
    'pronta':          '✅',
    'occupata':        '🛏️',
    'non_disponibile': '🚫',
}
LABEL_STATO = {
    'checkout_ok':     'Check-out ok',
    'da_pulire':       'Da pulire',
    'pronta':          'Pronta',
    'occupata':        'Occupata',
    'non_disponibile': 'Non disponibile',
}


def _cors_headers(origin):
    allow = origin if origin in ALLOWED_ORIGINS else 'https://gardenhub.it'
    return {
        'Access-Control-Allow-Origin':  allow,
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
    }


def _json_response(origin, payload, status=200):
    return (json.dumps(payload), status, {**_cors_headers(origin), 'Content-Type': 'application/json'})


def _tokens_attivi():
    db = firestore.client()
    tokens = set()
    for doc in db.collection('staffTokens').stream():
        d = doc.to_dict() or {}
        if d.get('notifiche'):
            tokens.update(d.get('tokens', []) or [])
    return list(tokens)


def _rimuovi_token_morto(token):
    # FCM ha risposto "non registrato": il token è invalido in modo permanente
    # (browser aggiornato, dati puliti, ecc.) — lo togliamo da staffTokens così
    # un operatore risulta "senza notifiche attive" invece di sembrare attivo
    # mentre in realtà non riceve più nulla (stesso comportamento di
    # notifiche-ristorazione).
    db = firestore.client()
    for doc in db.collection('staffTokens').where('tokens', 'array_contains', token).stream():
        try:
            doc.reference.update({'tokens': firestore.ArrayRemove([token])})
            print(f'Token morto rimosso da {doc.id}: {token[:24]}...')
        except Exception as e:
            print(f'Errore rimozione token morto da {doc.id}: {e}')


def _invia(tokens, title, body, tag, link):
    inviate = 0
    for tok in tokens:
        msg = messaging.Message(
            token=tok,
            webpush=messaging.WebpushConfig(
                notification=messaging.WebpushNotification(
                    title=title,
                    body=body,
                    icon=f'{SITE_URL}/logo-hub-app.jpg',
                    badge=f'{SITE_URL}/logo-hub-app.jpg',
                    tag=tag,
                    require_interaction=True,
                ),
                fcm_options=messaging.WebpushFCMOptions(link=link),
            ),
        )
        try:
            messaging.send(msg)
            inviate += 1
        except messaging.UnregisteredError:
            print(f'Token non registrato, rimosso: {tok[:24]}...')
            _rimuovi_token_morto(tok)
        except Exception as e:
            print(f'Errore invio a {tok[:24]}...: {e}')
    return inviate


def _messaggio_cambio_stato(alloggio, nuovo_stato, op):
    emoji = EMOJI_STATO.get(nuovo_stato, '🏠')
    label = LABEL_STATO.get(nuovo_stato, nuovo_stato or '')
    title = f'{emoji} {alloggio} · {label}'
    body  = f'Aggiornato da {op}' if op else 'Stato aggiornato'
    return title, body


@functions_framework.http
def invia_notifica_pulizie(request):
    origin = request.headers.get('Origin', '')

    if request.method == 'OPTIONS':
        return ('', 204, _cors_headers(origin))

    if request.method != 'POST':
        return _json_response(origin, {'ok': False, 'errore': 'metodo non permesso'}, 405)

    data     = request.get_json(silent=True) or {}
    evento   = data.get('evento')
    tokens   = _tokens_attivi()

    if evento == 'cambio_stato':
        alloggio_id   = data.get('alloggio_id') or ''
        alloggio_nome = data.get('alloggio_nome') or 'Alloggio'
        nuovo_stato   = data.get('nuovo_stato') or ''
        op            = data.get('op') or ''

        title, body = _messaggio_cambio_stato(alloggio_nome, nuovo_stato, op)
        inviate = _invia(tokens, title, body, f'alloggio-stato-{alloggio_id or alloggio_nome}', f'{SITE_URL}/alloggi/')
        return _json_response(origin, {'ok': True, 'inviate': inviate})

    if evento == 'test':
        chi = data.get('richiesto_da') or 'Staff'
        title = '🔔 Notifica di test'
        body  = f'Le notifiche push funzionano correttamente (richiesta da {chi})'
        inviate = _invia(tokens, title, body, f'test-{int(time.time())}', f'{SITE_URL}/alloggi/')
        return _json_response(origin, {'ok': True, 'inviate': inviate})

    return _json_response(origin, {'ok': False, 'errore': 'evento non valido'}, 400)
