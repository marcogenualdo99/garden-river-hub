"""Bot Telegram Garden Hub — notifiche su chat separate per reparto.

Un solo bot, quattro gruppi Telegram: manutenzione, navetta, pulizie, reception.
Ogni gruppo si collega scrivendo nel gruppo:   /collega <reparto> <codice>
Il collegamento (reparto -> chat_id) vive in Firestore, doc `impostazioni/telegram`
(scritto solo da questa funzione, Admin SDK).

Un unico entry point HTTP (`telegram_bot`) fa due cose:
  1. Webhook di Telegram (riconosciuto dall'header X-Telegram-Bot-Api-Secret-Token):
     comandi /collega, /scollega, /stato, /start.
  2. Eventi dall'Hub (POST JSON con "evento"): il messaggio e' formattato qui,
     il chiamante non puo' mandare testo libero.

Env: TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, TELEGRAM_SETUP_CODE.
"""

import html
import json
import os
import urllib.request

import firebase_admin
from firebase_admin import firestore
import functions_framework

if not firebase_admin._apps:
    firebase_admin.initialize_app()

BOT_TOKEN       = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
WEBHOOK_SECRET  = os.environ.get('TELEGRAM_WEBHOOK_SECRET', '').strip()
SETUP_CODE      = os.environ.get('TELEGRAM_SETUP_CODE', '').strip()
SITE_URL        = 'https://www.gardenhub.it'
ALLOWED_ORIGINS = {'https://gardenhub.it', 'https://www.gardenhub.it'}

REPARTI = {
    'manutenzione': '🔧 Manutenzione',
    'navetta':      '🚐 Navetta',
    'pulizie':      '🧹 Pulizie',
    'reception':    '🛎️ Reception',
}

EMOJI_STATO = {'checkout_ok': '🧹', 'da_pulire': '🧹', 'pronta': '✅', 'occupata': '🛏️', 'non_disponibile': '🚫'}
LABEL_STATO = {'checkout_ok': 'Check-out ok', 'da_pulire': 'Da pulire', 'pronta': 'Pronta',
               'occupata': 'Occupata', 'non_disponibile': 'Non disponibile'}


def _cors(origin):
    return {
        'Access-Control-Allow-Origin':  origin if origin in ALLOWED_ORIGINS else 'https://gardenhub.it',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
    }


def _json(origin, payload, status=200):
    return (json.dumps(payload), status, {**_cors(origin), 'Content-Type': 'application/json'})


def _e(v, n=200):
    """Testo dell'utente -> sicuro per parse_mode HTML, accorciato."""
    return html.escape(str(v or '').strip()[:n])


def _tg(metodo, payload):
    req = urllib.request.Request(
        f'https://api.telegram.org/bot{BOT_TOKEN}/{metodo}',
        data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def _doc():
    return firestore.client().collection('impostazioni').document('telegram')


def _canali():
    snap = _doc().get()
    return ((snap.to_dict() or {}).get('canali') or {}) if snap.exists else {}


def _scrivi_canale(reparto, chat_id, titolo=''):
    _doc().set({'canali': {reparto: {'chat_id': chat_id, 'titolo': titolo} if chat_id else firestore.DELETE_FIELD}}, merge=True)


def _invia(reparti, testo):
    """Manda `testo` (HTML) ai gruppi dei reparti indicati. Ritorna quanti messaggi sono partiti."""
    if not BOT_TOKEN:
        print('TELEGRAM_BOT_TOKEN non configurato')
        return 0
    canali, inviati, visti = _canali(), 0, set()
    for r in reparti:
        chat = (canali.get(r) or {}).get('chat_id')
        if not chat or chat in visti:
            continue
        visti.add(chat)
        try:
            _tg('sendMessage', {'chat_id': chat, 'text': testo, 'parse_mode': 'HTML', 'disable_web_page_preview': True})
            inviati += 1
        except Exception as ex:
            print(f'Invio Telegram a {r} fallito: {ex}')
    return inviati


# ── Comandi ricevuti dal bot ───────────────────────────────────────────────

def _risposta(chat_id, testo):
    try:
        _tg('sendMessage', {'chat_id': chat_id, 'text': testo, 'parse_mode': 'HTML'})
    except Exception as ex:
        print(f'Risposta Telegram fallita: {ex}')


def _comando(msg):
    chat = msg.get('chat') or {}
    chat_id = chat.get('id')
    testo = (msg.get('text') or '').strip()
    if not chat_id or not testo.startswith('/'):
        return
    parti = testo.split()
    cmd = parti[0].split('@')[0].lower()
    elenco = ', '.join(REPARTI)

    if cmd in ('/start', '/help'):
        _risposta(chat_id, 'Bot Garden Hub.\nIn un gruppo scrivi <code>/collega &lt;reparto&gt; &lt;codice&gt;</code>\n'
                           f'Reparti: {elenco}\nAltri comandi: /stato, /scollega')
    elif cmd == '/collega':
        if chat.get('type') == 'private':
            return _risposta(chat_id, 'Il collegamento va fatto dentro il gruppo del reparto, non in privato.')
        reparto = (parti[1] if len(parti) > 1 else '').lower()
        codice = parti[2] if len(parti) > 2 else ''
        if reparto not in REPARTI:
            return _risposta(chat_id, f'Reparto non valido. Scegli tra: {elenco}')
        if not SETUP_CODE or codice != SETUP_CODE:
            return _risposta(chat_id, 'Codice di collegamento errato.')
        _scrivi_canale(reparto, chat_id, chat.get('title', ''))
        _risposta(chat_id, f'✅ Gruppo collegato a <b>{REPARTI[reparto]}</b>. Da ora le notifiche arrivano qui.')
    elif cmd == '/scollega':
        codice = parti[1] if len(parti) > 1 else ''
        if not SETUP_CODE or codice != SETUP_CODE:
            return _risposta(chat_id, 'Per scollegare: <code>/scollega &lt;codice&gt;</code>')
        tolti = [r for r, c in _canali().items() if (c or {}).get('chat_id') == chat_id]
        for r in tolti:
            _scrivi_canale(r, None)
        _risposta(chat_id, 'Gruppo scollegato.' if tolti else 'Questo gruppo non era collegato.')
    elif cmd == '/stato':
        mio = [REPARTI[r] for r, c in _canali().items() if (c or {}).get('chat_id') == chat_id and r in REPARTI]
        _risposta(chat_id, ('Questo gruppo riceve: ' + ', '.join(mio)) if mio else 'Questo gruppo non è collegato a nessun reparto.')


# ── Eventi dall'Hub ────────────────────────────────────────────────────────

def _evento(data):
    ev = data.get('evento')
    if ev == 'ticket':
        urgente = data.get('priority') == 'alta'
        riga = ' — '.join(x for x in (_e(data.get('category'), 60), _e(data.get('issue_description'), 300)) if x)
        t = f"{'🚨 <b>URGENTE</b> · ' if urgente else '🔧 '}<b>Nuovo ticket: {_e(data.get('housing_unit'), 60) or 'Alloggio'}</b>\n{riga}\n{SITE_URL}/manutenzione/"
        return _invia(['manutenzione'], t)
    if ev == 'cambio_stato':
        stato = data.get('nuovo_stato') or ''
        t = (f"{EMOJI_STATO.get(stato, '🏠')} <b>{_e(data.get('alloggio_nome'), 60) or 'Alloggio'}</b> · {_e(LABEL_STATO.get(stato, stato), 40)}"
             + (f"\nda {_e(data.get('op'), 60)}" if data.get('op') else ''))
        # L'alloggio pronto interessa anche alla reception (puo' assegnarlo all'arrivo).
        return _invia(['pulizie', 'reception'] if stato == 'pronta' else ['pulizie'], t)
    if ev == 'navetta':
        extra = ' · '.join(x for x in (
            f"{int(data['persone'])} pers." if str(data.get('persone') or '').isdigit() else '',
            f"autista {_e(data.get('autista_nome'), 40)}" if data.get('autista_nome') else '') if x)
        t = (f"🚐 <b>Corsa navetta {_e(data.get('orario'), 5)}</b>\n"
             f"{_e(data.get('nome'), 60)} · {_e(data.get('alloggio_nome'), 40) or '—'}\n"
             f"Spiaggia: {_e(data.get('spiaggia_nome'), 60) or '—'}" + (f"\n{extra}" if extra else ''))
        return _invia(['navetta'], t)
    if ev == 'checkin':
        t = (f"🛎️ <b>Check-in online ricevuto</b>\n{_e(data.get('nome'), 60)} · {_e(data.get('alloggio_nome'), 40) or '—'}\n"
             f"{_e(data.get('persone'), 3)} persone — verifica i documenti nel Calendario\n{SITE_URL}/calendario/")
        return _invia(['reception'], t)
    if ev == 'test':
        t = f"🔔 Notifica di test (richiesta da {_e(data.get('richiesto_da'), 40) or 'Staff'})"
        return _invia(list(REPARTI), t)
    return None


@functions_framework.http
def telegram_bot(request):
    origin = request.headers.get('Origin', '')
    if request.method == 'OPTIONS':
        return ('', 204, _cors(origin))
    if request.method != 'POST':
        return _json(origin, {'ok': False, 'errore': 'metodo non permesso'}, 405)

    data = request.get_json(silent=True) or {}

    secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
    if secret is not None:  # chiamata di Telegram
        if not WEBHOOK_SECRET or secret != WEBHOOK_SECRET:
            return ('', 403)
        msg = data.get('message') or data.get('channel_post') or {}
        try:
            _comando(msg)
        except Exception as ex:
            print(f'Errore comando: {ex}')
        return ('', 200)  # sempre 200, altrimenti Telegram riprova all'infinito

    inviati = _evento(data)
    if inviati is None:
        return _json(origin, {'ok': False, 'errore': 'evento non valido'}, 400)
    return _json(origin, {'ok': True, 'inviati': inviati})
