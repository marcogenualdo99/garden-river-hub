import json
import time

import firebase_admin
from firebase_admin import firestore, messaging
import functions_framework

if not firebase_admin._apps:
    firebase_admin.initialize_app()

SITE_URL        = 'https://www.gardenhub.it'
ALLOWED_ORIGINS = {'https://gardenhub.it', 'https://www.gardenhub.it'}


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
    # (browser aggiornato, dati puliti, ecc.) e non tornerà mai valido da solo —
    # lo togliamo da staffTokens così un operatore risulta "senza notifiche
    # attive" invece di sembrare attivo mentre in realtà non riceve più nulla
    # (stesso comportamento di notifiche-pulizie e notifiche-ristorazione).
    db = firestore.client()
    for doc in db.collection('staffTokens').where('tokens', 'array_contains', token).stream():
        try:
            doc.reference.update({'tokens': firestore.ArrayRemove([token])})
            print(f'Token morto rimosso da {doc.id}: {token[:24]}...')
        except Exception as e:
            print(f'Errore rimozione token morto da {doc.id}: {e}')


def _invia(tokens, title, body, tag):
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
                fcm_options=messaging.WebpushFCMOptions(link=f'{SITE_URL}/manutenzione/'),
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


def _messaggio_ticket(housing_unit, category, issue_description, priority=None):
    emoji = '🚨 URGENTE' if priority == 'alta' else '🔧'
    title = f'{emoji} Nuovo ticket: {housing_unit or "Alloggio"}'
    dettaglio = f'{category or "Manutenzione"} — {issue_description}' if issue_description else (category or 'Manutenzione')
    body = dettaglio if len(dettaglio) <= 120 else dettaglio[:117] + '…'
    return title, body


@functions_framework.http
def invia_notifica_manutenzione(request):
    origin = request.headers.get('Origin', '')

    if request.method == 'OPTIONS':
        return ('', 204, _cors_headers(origin))

    if request.method != 'POST':
        return _json_response(origin, {'ok': False, 'errore': 'metodo non permesso'}, 405)

    data   = request.get_json(silent=True) or {}
    evento = data.get('evento')
    tokens = _tokens_attivi()

    if evento == 'ticket':
        doc_id            = data.get('doc_id') or 'ticket'
        housing_unit      = data.get('housing_unit') or ''
        category          = data.get('category') or ''
        issue_description = data.get('issue_description') or ''
        priority          = data.get('priority') or 'normale'

        title, body = _messaggio_ticket(housing_unit, category, issue_description, priority)
        inviate = _invia(tokens, title, body, f'ticket-{doc_id}')

        # Marca il ticket come notificato, così il controllo periodico di
        # sicurezza non lo rispedisce una seconda volta se questa chiamata è
        # già andata a buon fine (stesso schema di notifiche-ristorazione).
        if data.get('doc_id'):
            try:
                db = firestore.client()
                db.collection('maintenance_tickets').document(doc_id).update({'notified': True})
            except Exception as e:
                print(f'Errore marcatura notified per {doc_id}: {e}')

        return _json_response(origin, {'ok': True, 'inviate': inviate})

    if evento == 'test':
        chi   = data.get('richiesto_da') or 'Staff'
        title = '🔔 Notifica di test'
        body  = f'Le notifiche push funzionano correttamente (richiesta da {chi})'
        inviate = _invia(tokens, title, body, f'test-{int(time.time())}')
        return _json_response(origin, {'ok': True, 'inviate': inviate})

    if evento == 'controlla_pendenti':
        # Chiamato periodicamente da Cloud Scheduler — rete di sicurezza per i
        # ticket la cui notifica istantanea dal browser non è mai arrivata.
        db = firestore.client()
        pendenti = list(db.collection('maintenance_tickets').where('notified', '==', False).stream())
        processati = 0
        for doc in pendenti:
            t = doc.to_dict() or {}
            title, body = _messaggio_ticket(t.get('housing_unit'), t.get('category'), t.get('issue_description'), t.get('priority'))
            _invia(tokens, title, body, f'ticket-{doc.id}')
            try:
                doc.reference.update({'notified': True})
            except Exception as e:
                print(f'Errore marcatura notified per {doc.id}: {e}')
            processati += 1
        return _json_response(origin, {'ok': True, 'processati': processati})

    return _json_response(origin, {'ok': False, 'errore': 'evento non valido'}, 400)
