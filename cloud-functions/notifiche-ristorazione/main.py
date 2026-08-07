import datetime
import json
import time
from zoneinfo import ZoneInfo

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


def _label_giorno(data_iso):
    try:
        target = datetime.date.fromisoformat(data_iso)
    except (ValueError, TypeError):
        return data_iso or ''
    oggi = datetime.datetime.now(ZoneInfo('Europe/Rome')).date()
    if target == oggi:
        return 'oggi'
    if target == oggi + datetime.timedelta(days=1):
        return 'domani'
    return target.strftime('%d/%m')


def _famiglie_senza_ordine(db, target_date, tipo):
    altro_pasto = 'cena' if tipo == 'pranzo' else 'pranzo'

    famiglie = [d.to_dict() | {'id': d.id} for d in db.collection('famiglie_ristorazione').stream()]

    ordini_correnti = {
        (o.to_dict() or {}).get('famiglia_id')
        for o in db.collection('ordini_ristorazione')
            .where('data', '==', target_date).where('tipo', '==', tipo).stream()
    }
    ordini_altro = {
        (o.to_dict() or {}).get('famiglia_id')
        for o in db.collection('ordini_ristorazione')
            .where('data', '==', target_date).where('tipo', '==', altro_pasto).stream()
    }

    mancanti = 0
    for f in famiglie:
        checkin  = f.get('checkin')
        checkout = f.get('checkout')
        if checkin and checkin > target_date:
            continue  # non ancora arrivata
        if checkout and checkout <= target_date:
            continue  # parte oggi o già partita
        if checkin == target_date:
            if f.get('ora_arrivo') == 'dopo_pranzo' and tipo == 'pranzo':
                continue
            if f.get('ora_arrivo') == 'sera':
                continue

        ha_corrente = f['id'] in ordini_correnti
        if f.get('trattamento') == 'MP':
            ha_altro = f['id'] in ordini_altro
            if not ha_corrente and not ha_altro:
                mancanti += 1
        elif not ha_corrente:
            mancanti += 1

    return mancanti


def _messaggio_ordine(db, famiglia, tipo, giorno):
    pasto = {'pranzo': 'Pranzo', 'cena': 'Cena'}.get(tipo, tipo or 'Pasto')
    title = f'🍽️ Nuovo ordine: {famiglia}'

    if giorno:
        mancanti = _famiglie_senza_ordine(db, giorno, tipo)
        giorno_label = _label_giorno(giorno)
        if mancanti == 0:
            body = f'{pasto} di {giorno_label} — tutte le famiglie hanno ordinato ✓'
        else:
            plurale = 'a' if mancanti == 1 else 'e'
            body = f"{pasto} di {giorno_label} — mancano ancora {mancanti} famigli{plurale} all'appello"
    else:
        body = f'{pasto} — nuovo ordine ricevuto'

    return title, body


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
    # attive" invece di sembrare attivo mentre in realtà non riceve più nulla.
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
                fcm_options=messaging.WebpushFCMOptions(link=f'{SITE_URL}/ristorazione/staff.html'),
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


@functions_framework.http
def invia_notifica_ristorazione(request):
    origin = request.headers.get('Origin', '')

    if request.method == 'OPTIONS':
        return ('', 204, _cors_headers(origin))

    if request.method != 'POST':
        return _json_response(origin, {'ok': False, 'errore': 'metodo non permesso'}, 405)

    data   = request.get_json(silent=True) or {}
    evento = data.get('evento')
    tokens = _tokens_attivi()

    if evento == 'ordine':
        famiglia = data.get('famiglia_nome') or 'Ospite sconosciuto'
        tipo     = data.get('tipo') or ''
        giorno   = data.get('data') or ''
        doc_id   = data.get('doc_id') or 'ordine'

        db = firestore.client()
        title, body = _messaggio_ordine(db, famiglia, tipo, giorno)
        inviate = _invia(tokens, title, body, f'ordine-{doc_id}')

        # Marca l'ordine come notificato, così il controllo periodico di sicurezza
        # non lo rispedisce una seconda volta se questa chiamata è già andata a buon fine.
        if data.get('doc_id'):
            try:
                db.collection('ordini_ristorazione').document(doc_id).update({'notified': True})
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
        # Chiamato periodicamente da Cloud Scheduler — rete di sicurezza per gli
        # ordini la cui notifica istantanea dal browser non è mai arrivata.
        db = firestore.client()
        pendenti = list(db.collection('ordini_ristorazione').where('notified', '==', False).stream())
        processati = 0
        for doc in pendenti:
            f = doc.to_dict() or {}
            famiglia = f.get('famiglia_nome') or 'Ospite sconosciuto'
            tipo     = f.get('tipo') or ''
            giorno   = f.get('data') or ''
            title, body = _messaggio_ordine(db, famiglia, tipo, giorno)
            _invia(tokens, title, body, f'ordine-{doc.id}')
            try:
                doc.reference.update({'notified': True})
            except Exception as e:
                print(f'Errore marcatura notified per {doc.id}: {e}')
            processati += 1
        return _json_response(origin, {'ok': True, 'processati': processati})

    return _json_response(origin, {'ok': False, 'errore': 'evento non valido'}, 400)
