"""Bot Telegram Garden Hub — notifiche su chat separate per reparto.

Un solo bot, cinque gruppi Telegram: manutenzione, navetta, pulizie, reception, ristorazione.
Ogni gruppo si collega scrivendo nel gruppo:   /collega <reparto> <codice>
Il collegamento (reparto -> chat_id) vive in Firestore, doc `impostazioni/telegram`
(scritto solo da questa funzione, Admin SDK).

Un unico entry point HTTP (`telegram_bot`) fa due cose:
  1. Webhook di Telegram (riconosciuto dall'header X-Telegram-Bot-Api-Secret-Token):
     comandi /collega, /scollega, /stato, /start.
  2. Eventi dall'Hub (POST JSON con "evento"): il messaggio e' formattato qui,
     il chiamante non puo' mandare testo libero.

Env: TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, TELEGRAM_SETUP_CODE, CRON_TOKEN
(CRON_TOKEN: segreto che Cloud Scheduler passa in `_cron_token` per gli eventi
programmati `promemoria_ticket`, `riepilogo_mattina`, `ordini_pendenti`, `risto_sollecito`, `risto_riepilogo` e `risto_domani`; senza, questi eventi sono rifiutati).
"""

import hmac
import html
import json
import os
import re
import unicodedata
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

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
    'ristorazione': '🍽️ Ristorazione',
    'market':       '🛍️ Market',
}

EMOJI_STATO = {'checkout_ok': '🧹', 'da_pulire': '🧹', 'pronta': '✅', 'occupata': '🛏️', 'non_disponibile': '🚫'}
LABEL_STATO = {'checkout_ok': 'Check-out ok', 'da_pulire': 'Da pulire', 'pronta': 'Pronta',
               'occupata': 'Occupata', 'non_disponibile': 'Non disponibile'}


def _cors(origin):
    return {
        'Access-Control-Allow-Origin':  origin if origin in ALLOWED_ORIGINS else 'https://gardenhub.it',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Internal-Token',
    }


def _json(origin, payload, status=200):
    return (json.dumps(payload), status, {**_cors(origin), 'Content-Type': 'application/json'})


def _norm(v):
    """Nome autista -> chiave stabile (minuscole, solo lettere/numeri)."""
    s = unicodedata.normalize('NFKD', str(v or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]', '', s)


def _etichetta(chiave, c):
    if chiave.startswith('navetta:'):
        return f"🚐 Navetta · {(c or {}).get('autista') or chiave[8:]}"
    return REPARTI.get(chiave, chiave)


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


def _scrivi_canale(reparto, chat_id, titolo='', autista=''):
    valore = {'chat_id': chat_id, 'titolo': titolo}
    if autista:
        valore['autista'] = autista
    _doc().set({'canali': {reparto: valore if chat_id else firestore.DELETE_FIELD}}, merge=True)


def _notifica_app(reparti, testo):
    """Copia dell'avviso per l'app Garden Hub (V2): doc in `notifiche`, letto dai client con
    gli stessi reparti di Telegram. Si tengono solo le ultime 24 ore. Mai bloccante."""
    try:
        db = firestore.client()
        adesso = datetime.now(timezone.utc)
        pulito = html.unescape(re.sub(r'<[^>]+>', '', testo or '')).strip()
        righe = [r.strip() for r in pulito.split('\n') if r.strip()]
        db.collection('notifiche').add({
            'reparti': [r for r in reparti if r],
            'titolo': righe[0][:120] if righe else '',
            'testo': '\n'.join(righe[1:])[:400] if len(righe) > 1 else (righe[0][:400] if righe else ''),
            'ts': adesso,
        })
        for vecchia in db.collection('notifiche').where('ts', '<', adesso - timedelta(hours=24)).limit(50).stream():
            vecchia.reference.delete()
    except Exception as ex:
        print(f'Copia notifica per app fallita: {ex}')


def _invia(reparti, testo, primo_disponibile=False, tastiera=None):
    """Manda `testo` (HTML) ai gruppi indicati (chiavi dei canali). Con
    primo_disponibile ci si ferma al primo gruppo collegato (es. gruppo
    dell'autista, altrimenti gruppo navetta generico). Ritorna i messaggi partiti."""
    _notifica_app(list(reparti), testo)
    if not BOT_TOKEN:
        print('TELEGRAM_BOT_TOKEN non configurato')
        return 0
    canali, inviati, visti = _canali(), 0, set()
    if primo_disponibile:
        reparti = [next((r for r in reparti if (canali.get(r) or {}).get('chat_id')), None)]
    for r in reparti:
        if r is None:
            continue
        chat = (canali.get(r) or {}).get('chat_id')
        if not chat or chat in visti:
            continue
        visti.add(chat)
        try:
            payload = {'chat_id': chat, 'text': testo, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
            if tastiera:
                payload['reply_markup'] = {'inline_keyboard': tastiera}
            _tg('sendMessage', payload)
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
                           f'Reparti: {elenco}\nAltri comandi: /stato, /scollega\nNavetta di un autista: <code>/collega navetta &lt;codice&gt; &lt;Nome autista&gt;</code>')
    elif cmd == '/collega':
        if chat.get('type') == 'private':
            return _risposta(chat_id, 'Il collegamento va fatto dentro il gruppo del reparto, non in privato.')
        reparto = (parti[1] if len(parti) > 1 else '').lower()
        codice = parti[2] if len(parti) > 2 else ''
        autista = ' '.join(parti[3:]).strip()
        if reparto not in REPARTI:
            return _risposta(chat_id, f'Reparto non valido. Scegli tra: {elenco}')
        if not SETUP_CODE or codice != SETUP_CODE:
            return _risposta(chat_id, 'Codice di collegamento errato.')
        if autista and reparto != 'navetta':
            return _risposta(chat_id, 'Il nome dell\'autista si indica solo per la navetta.')
        if autista:
            chiave = f'navetta:{_norm(autista)}'
            if chiave == 'navetta:':
                return _risposta(chat_id, 'Nome autista non valido.')
            _scrivi_canale(chiave, chat_id, chat.get('title', ''), autista)
            return _risposta(chat_id, f'✅ Gruppo collegato alla navetta di <b>{_e(autista, 40)}</b>. Qui arrivano solo le sue corse.')
        _scrivi_canale(reparto, chat_id, chat.get('title', ''))
        extra = ' (riceve le corse degli autisti che non hanno un gruppo proprio)' if reparto == 'navetta' else ''
        _risposta(chat_id, f'✅ Gruppo collegato a <b>{REPARTI[reparto]}</b>{extra}. Da ora le notifiche arrivano qui.')
    elif cmd == '/scollega':
        codice = parti[1] if len(parti) > 1 else ''
        if not SETUP_CODE or codice != SETUP_CODE:
            return _risposta(chat_id, 'Per scollegare: <code>/scollega &lt;codice&gt;</code>')
        tolti = [r for r, c in _canali().items() if (c or {}).get('chat_id') == chat_id]
        for r in tolti:
            _scrivi_canale(r, None)
        _risposta(chat_id, 'Gruppo scollegato.' if tolti else 'Questo gruppo non era collegato.')
    elif cmd == '/stato':
        mio = [_etichetta(r, c) for r, c in _canali().items() if (c or {}).get('chat_id') == chat_id]
        _risposta(chat_id, ('Questo gruppo riceve: ' + ', '.join(mio)) if mio else 'Questo gruppo non è collegato a nessun reparto.')


# ── Pulsanti (callback) ────────────────────────────────────────────────────

def _callback(cq):
    """Pulsante 'Segna come risolto' sotto un ticket: aggiorna l'Hub."""
    msg = cq.get('message') or {}
    chat_id = (msg.get('chat') or {}).get('id')
    dati = cq.get('data') or ''
    cid = cq.get('id')
    if dati == 'noop':
        return _tg('answerCallbackQuery', {'callback_query_id': cid})
    if dati.startswith('shop:'):
        return _callback_shop(cq, dati, chat_id, msg, cid)
    if not dati.startswith('risolto:'):
        return _tg('answerCallbackQuery', {'callback_query_id': cid})
    # Solo dal gruppo Manutenzione collegato: nessun altro chat puo' chiudere ticket.
    if not chat_id or (_canali().get('manutenzione') or {}).get('chat_id') != chat_id:
        return _tg('answerCallbackQuery', {'callback_query_id': cid, 'text': 'Non autorizzato', 'show_alert': True})
    ticket_id = dati.split(':', 1)[1]
    chi = ((cq.get('from') or {}).get('first_name') or 'Staff')[:40]
    ref = firestore.client().collection('maintenance_tickets').document(ticket_id)
    if not ref.get().exists:
        return _tg('answerCallbackQuery', {'callback_query_id': cid, 'text': 'Ticket non trovato (forse eliminato)', 'show_alert': True})
    ref.update({'status': True, 'risolto_da': f'{chi} (Telegram)', 'risolto_il': datetime.now(ZoneInfo('Europe/Rome')).isoformat()})
    ora = datetime.now(ZoneInfo('Europe/Rome')).strftime('%H:%M')
    _tg('answerCallbackQuery', {'callback_query_id': cid, 'text': 'Ticket segnato come risolto'})
    _tg('editMessageReplyMarkup', {'chat_id': chat_id, 'message_id': msg.get('message_id'),
        'reply_markup': {'inline_keyboard': [[{'text': f'✅ Risolto da {chi} · {ora}', 'callback_data': 'noop'}]]}})


# ── Market (shop interno) ──────────────────────────────────────────────────
SHOP_STATI = {'nuovo': '🆕 Ricevuto', 'pronto': '✅ Pronto', 'consegnato': '📦 Consegnato', 'annullato': '❌ Annullato'}


def _eur(v):
    try:
        return '€ ' + f'{float(v):.2f}'.replace('.', ',')
    except (TypeError, ValueError):
        return '€ —'


def _shop_testo(o, chi=''):
    righe = '\n'.join(f"• {int(r.get('quantita') or 0)} × {_e(r.get('titolo'), 80)} — {_eur(r.get('importo'))}"
                      for r in (o.get('righe') or []) if isinstance(r, dict))
    pagato = (o.get('pagamento') or {}).get('stato') == 'pagato'
    stato = o.get('stato') or 'nuovo'
    if o.get('modalita') == 'consegna':
        g = str(o.get('consegna_data') or '')
        gg = f"{g[8:10]}/{g[5:7]}" if len(g) >= 10 else ''
        dove = f"🚚 <b>Consegna in alloggio</b> · {gg} {_e(o.get('consegna_fascia'), 11).replace('-', ' – ')}"
    else:
        dove = '🏊 <b>Ritiro al Bar piscina</b>'
    tel = _e(o.get('ospite_tel'), 40)
    return (f"{'🛍️ <b>Nuovo ordine Market</b>' if stato == 'nuovo' else '🛍️ <b>Ordine Market</b>'}\n\n"
            f"👤 {_e(o.get('ospite_nome'), 80) or '—'} · 🏠 {_e(o.get('alloggio'), 60) or '—'}\n"
            + (f"📞 {tel}\n" if tel else '') +
            f"\n{righe}\n\n"
            f"💶 <b>Totale {_eur(o.get('totale'))}</b> · {('✅ pagato' + {'paypal': ' con carta (PayPal)'}.get((o.get('pagamento') or {}).get('metodo'), '')) if pagato else 'da pagare ' + {'contanti': 'in contanti', 'paypal': 'con carta (PayPal)'}.get((o.get('pagamento') or {}).get('metodo'), '')}\n{dove}\n"
            + (f"📝 {_e(o.get('note'), 300)}\n" if o.get('note') else '') +
            f"\n📌 <b>Stato:</b> {SHOP_STATI.get(stato, stato)}" + (f" · {_e(chi, 40)}" if chi and stato != 'nuovo' else ''))


def _shop_tastiera(doc_id, o):
    stato = o.get('stato') or 'nuovo'
    pagato = (o.get('pagamento') or {}).get('stato') == 'pagato'
    if stato == 'annullato':
        return [[{'text': '❌ Ordine annullato', 'callback_data': 'noop'}]]
    righe = []
    if stato == 'nuovo':
        righe.append([{'text': '✅ Pronto', 'callback_data': f'shop:pronto:{doc_id}'}, {'text': '📦 Consegnato', 'callback_data': f'shop:consegnato:{doc_id}'}])
    elif stato == 'pronto':
        righe.append([{'text': '📦 Consegnato', 'callback_data': f'shop:consegnato:{doc_id}'}])
    ultima = []
    if not pagato:
        ultima.append({'text': '💶 Segna pagato', 'callback_data': f'shop:pagato:{doc_id}'})
    if stato in ('nuovo', 'pronto'):
        ultima.append({'text': '❌ Annulla', 'callback_data': f'shop:annullato:{doc_id}'})
    if ultima:
        righe.append(ultima)
    return righe or [[{'text': '📦 Consegnato e pagato', 'callback_data': 'noop'}]]


def _notifica_shop(data):
    doc_id = str(data.get('doc_id') or '')[:40]
    o = {**data, 'stato': 'nuovo', 'pagamento': {'stato': 'pagato' if data.get('pagato') else 'da_pagare', 'metodo': data.get('metodo')}}
    return _invia(['market'], _shop_testo(o), tastiera=_shop_tastiera(doc_id, o) if doc_id else None)


def _callback_shop(cq, dati, chat_id, msg, cid):
    """Pulsanti sotto un ordine del Market: cambia lo stato in Firestore e aggiorna il messaggio."""
    def risp(testo='', alert=False):
        return _tg('answerCallbackQuery', {'callback_query_id': cid, **({'text': testo, 'show_alert': alert} if testo else {})})
    if not chat_id or (_canali().get('market') or {}).get('chat_id') != chat_id:
        return risp('Non autorizzato', True)
    parti = dati.split(':', 2)
    if len(parti) != 3 or parti[1] not in ('pronto', 'consegnato', 'annullato', 'pagato'):
        return risp()
    azione, oid = parti[1], parti[2]
    db = firestore.client()
    ref = db.collection('shop_ordini').document(oid)
    snap = ref.get()
    if not snap.exists:
        return risp('Ordine non trovato (forse eliminato)', True)
    o = snap.to_dict() or {}
    chi = ((cq.get('from') or {}).get('first_name') or 'Staff')[:40]
    ora = datetime.now(ZoneInfo('Europe/Rome'))
    stato = o.get('stato') or 'nuovo'
    firma = {'aggiornato_da': f'{chi} (Telegram)', 'aggiornato_il': ora.isoformat()}
    if azione == 'pagato':
        if (o.get('pagamento') or {}).get('stato') == 'pagato':
            risp('Già segnato come pagato')
        else:
            ref.update({'pagamento.stato': 'pagato', 'pagamento.pagato_il': ora.isoformat(), **firma})
            o['pagamento'] = {**(o.get('pagamento') or {}), 'stato': 'pagato'}
            risp('Segnato come pagato')
    else:
        consentiti = {'nuovo': ('pronto', 'consegnato', 'annullato'), 'pronto': ('consegnato', 'annullato')}
        if azione not in consentiti.get(stato, ()):
            risp(f'Ordine già {SHOP_STATI.get(stato, stato)}', True)
        else:
            if azione == 'annullato':        # la giacenza dei prodotti torna disponibile
                for r in (o.get('righe') or []):
                    try:
                        pref = db.collection('shop_prodotti').document(str(r.get('id')))
                        ps = pref.get()
                        g = (ps.to_dict() or {}).get('giacenza') if ps.exists else None
                        if isinstance(g, (int, float)) and not isinstance(g, bool):
                            pref.update({'giacenza': firestore.Increment(int(r.get('quantita') or 0))})
                    except Exception as ex:
                        print(f'Ripristino giacenza fallito: {ex}')
            ref.update({'stato': azione, **firma})
            o['stato'] = azione
            risp({'pronto': 'Ordine pronto', 'consegnato': 'Ordine consegnato', 'annullato': 'Ordine annullato'}[azione])
    try:
        _tg('editMessageText', {'chat_id': chat_id, 'message_id': msg.get('message_id'), 'text': _shop_testo(o, chi),
                                'parse_mode': 'HTML', 'disable_web_page_preview': True,
                                'reply_markup': {'inline_keyboard': _shop_tastiera(oid, o)}})
    except Exception as ex:
        print(f'Aggiornamento messaggio ordine fallito: {ex}')


# ── Eventi dall'Hub ────────────────────────────────────────────────────────

def _evento(data):
    ev = data.get('evento')
    if ev == 'ticket':
        urgente = data.get('priority') == 'alta'
        da_ospite = data.get('origine') == 'ospite'
        quando = datetime.now(ZoneInfo('Europe/Rome')).strftime('%d/%m/%Y %H:%M')
        if da_ospite:
            tel = _e(data.get('telefono'), 40)
            t = (f"🧑‍🌾 <b>Nuovo ticket di manutenzione DALL'OSPITE</b>\n"
                 f"<i>Non arriva dalla reception: l'ha segnalato il cliente dall'Area ospite.</i>\n\n"
                 f"🏠 <b>Alloggio:</b> {_e(data.get('housing_unit'), 80) or '—'}\n"
                 f"🏷️ <b>Categoria:</b> {_e(data.get('category'), 80) or '—'}\n"
                 f"🔑 <b>Si può entrare in assenza dell'ospite:</b> {'Sì' if data.get('access_permission') else 'No'}\n"
                 + (f"⏰ <b>Orario richiesto (ospite presente):</b> {_e(data.get('fascia_oraria'), 11).replace('-', ' – ')}\n" if data.get('fascia_oraria') else '') +
                 f"🐾 <b>Animali in alloggio:</b> {'SÌ' if data.get('animali') else 'No'}\n"
                 f"👤 <b>Ospite:</b> {_e(data.get('operatore'), 80) or '—'}\n"
                 + (f"📞 <b>Telefono:</b> {tel}\n" if tel else '') +
                 f"🕐 <b>Quando:</b> {quando}\n\n"
                 f"📝 <b>Problema:</b>\n{_e(data.get('issue_description'), 2000) or '—'}")
        else:
            t = (f"{'🚨 <b>TICKET URGENTE</b>' if urgente else '🔧 <b>Nuovo ticket di manutenzione</b>'}\n\n"
                 f"🏠 <b>Alloggio:</b> {_e(data.get('housing_unit'), 80) or '—'}\n"
                 f"🏷️ <b>Categoria:</b> {_e(data.get('category'), 80) or '—'}\n"
                 f"⚡ <b>Priorità:</b> {'ALTA' if urgente else 'Normale'}\n"
                 f"🔑 <b>Accesso senza ospite:</b> {'Sì' if data.get('access_permission') else 'No'}\n"
                 + (f"⏰ <b>Orario richiesto (ospite presente):</b> {_e(data.get('fascia_oraria'), 11).replace('-', ' – ')}\n" if data.get('fascia_oraria') else '') +
                 f"🐾 <b>Animali in alloggio:</b> {'SÌ' if data.get('animali') else 'No'}\n"
                 f"👤 <b>Segnalato da:</b> {_e(data.get('operatore'), 60) or '—'}\n"
                 f"🕐 <b>Quando:</b> {quando}\n\n"
                 f"📝 <b>Problema:</b>\n{_e(data.get('issue_description'), 2000) or '—'}")
        doc_id = str(data.get('doc_id') or '')[:40]
        tastiera = [[{'text': '✅ Segna come risolto', 'callback_data': f'risolto:{doc_id}'}]] if doc_id else None
        return _invia(['manutenzione'], t, tastiera=tastiera)
    if ev == 'avviso_arrivo':
        quando = datetime.now(ZoneInfo('Europe/Rome')).strftime('%H:%M')
        t = (f"🛎️ <b>Cliente arrivato in struttura</b>\n"
             f"🏠 <b>Alloggio:</b> {_e(data.get('alloggio_nome'), 80) or '—'}\n"
             f"👤 <b>Ospite:</b> {_e(data.get('ospite'), 80) or '—'}\n"
             f"🕐 {quando} · segnalato da {_e(data.get('op'), 60) or 'Operatore'}")
        return _invia(['pulizie'], t)
    if ev == 'cambio_stato':
        stato = data.get('nuovo_stato') or ''
        if stato == 'da_pulire':
            op = _e(data.get('op'), 60) or 'Operatore'
            return _invia(['pulizie'], f"🏠 <b>{(_e(data.get('alloggio_nome'), 60) or 'Alloggio').upper()}</b>\n🧹 Check-out eseguito da {op}: da pulire")
        t = (f"🏠 <b>{(_e(data.get('alloggio_nome'), 60) or 'Alloggio').upper()}</b>\n{EMOJI_STATO.get(stato, '🏠')} {_e(LABEL_STATO.get(stato, stato), 40)}"
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
        # Gruppo dell'autista; se non ne ha uno, gruppo navetta generico.
        return _invia([f"navetta:{_norm(data.get('autista_nome'))}", 'navetta'], t, primo_disponibile=True)
    if ev == 'navetta_annullata':
        t = (f"❌ <b>Corsa navetta ANNULLATA · {_e(data.get('orario'), 5)}</b>\n"
             f"{_e(data.get('nome'), 60)} · {_e(data.get('alloggio_nome'), 40) or '—'}\n"
             f"Spiaggia: {_e(data.get('spiaggia_nome'), 60) or '—'}\n"
             f"Annullata da: {_e(data.get('annullata_da'), 60) or '—'}")
        return _invia([f"navetta:{_norm(data.get('autista_nome'))}", 'navetta'], t, primo_disponibile=True)
    if ev == 'checkin':
        t = (f"🛎️ <b>Check-in online ricevuto</b>\n{_e(data.get('nome'), 60)} · {_e(data.get('alloggio_nome'), 40) or '—'}\n"
             f"{_e(data.get('persone'), 3)} persone — verifica i documenti nel Calendario\n{SITE_URL}/calendario/")
        return _invia(['reception'], t)
    if ev == 'ordine':
        return _notifica_ordine(firestore.client(), str(data.get('doc_id') or '')[:120], data.get('famiglia_nome'), data.get('tipo'), data.get('data'),
                              data.get('piatti') if isinstance(data.get('piatti'), list) else None, data.get('note'), data.get('unita'))
    if ev == 'shop_ordine':
        return _notifica_shop(data)
    if ev == 'prenotazione':
        return _invia(['ristorazione'], _testo_prenotazione(data))
    if ev == 'test':
        t = f"🔔 Notifica di test (richiesta da {_e(data.get('richiesto_da'), 40) or 'Staff'})"
        return _invia(list(_canali()), t)
    return None


# ── Feed avvisi per l'app Android (anche con l'app chiusa) ─────────────────
# L'app Garden Hub (Sunmi V2) ha un servizio nativo che ogni ~20 secondi chiede qui i nuovi avvisi
# (copie dei messaggi Telegram, collezione `notifiche`) e li mostra come notifiche Android, senza
# bisogno che la pagina sia aperta. Autenticazione: chiave APP_FEED_KEY (variabile d'ambiente della CF),
# che l'app riceve da sola dopo il login di un operatore ('feed_chiave', riservato allo staff).

def _feed_autorizzato(request):
    chiave = os.environ.get('APP_FEED_KEY', '').strip()
    inviata = request.headers.get('X-App-Key', '')
    return bool(chiave and inviata and hmac.compare_digest(inviata, chiave))


def _feed_notifiche(data):
    db = firestore.client()
    adesso = datetime.now(timezone.utc)
    adesso_ms = int(adesso.timestamp() * 1000)
    try:
        since_ms = int(data.get('since') or 0)
    except (TypeError, ValueError):
        since_ms = 0
    if since_ms <= 0:                      # primo contatto: nessun arretrato, si parte da adesso
        return {'now': adesso_ms, 'items': []}
    since = datetime.fromtimestamp(since_ms / 1000.0, tz=timezone.utc)
    items = []
    try:
        for d in db.collection('notifiche').where('ts', '>', since).order_by('ts').limit(30).stream():
            x = d.to_dict() or {}
            ts = x.get('ts')
            items.append({'id': d.id, 'reparti': [str(r) for r in (x.get('reparti') or [])][:8],
                          'titolo': str(x.get('titolo') or '')[:120], 'testo': str(x.get('testo') or '')[:400],
                          'ts': int(ts.timestamp() * 1000) if ts else adesso_ms})
    except Exception as ex:
        print(f'Feed notifiche non riuscito: {ex}')
    return {'now': adesso_ms, 'items': items}


# ── Prenotazioni tavolo ────────────────────────────────────────────────────

def _testo_prenotazione(data):
    """Avviso al gruppo Ristorazione per una prenotazione tavolo nuova, modificata o annullata.
    Arriva dallo staff (pagina Ristorazione) o dall'ospite (Area ospite)."""
    azione = str(data.get('azione') or 'nuova')
    da_ospite = data.get('origine') == 'ospite'
    pasto = {'pranzo': 'Pranzo', 'cena': 'Cena'}.get(str(data.get('pasto') or ''), 'Pasto')
    quando = _label_giorno(str(data.get('data') or ''))
    persone = _e(data.get('persone'), 4)
    turno = _e(data.get('turno'), 8)
    if azione == 'annullata':
        titolo = '❌ <b>Prenotazione tavolo ANNULLATA</b>' + (" dall'ospite" if da_ospite else '')
    elif azione == 'modificata':
        titolo = '✏️ <b>Prenotazione tavolo modificata</b>' + (" dall'ospite" if da_ospite else '')
    else:
        titolo = '🍽️ <b>Nuova prenotazione tavolo</b>' + (" dall'Area ospite" if da_ospite else '')
    righe = [titolo]
    chi = _e(data.get('nome'), 80) or 'Ospite'
    alloggio = _e(data.get('alloggio'), 40)
    righe.append(f"👤 <b>{chi}</b>" + (f" · {alloggio}" if alloggio else '') + (' · cliente libero' if data.get('libera') else ''))
    righe.append(f"🕐 {pasto} di {quando}" + (f" · <b>{turno}</b>" if turno else '') + f" · <b>{persone} persone</b>")
    if data.get('tavolo'):
        righe.append(f"🪑 Tavolo {_e(data.get('tavolo'), 40)}")
    tel = _e(data.get('tel') or data.get('telefono'), 40)
    if tel:
        righe.append(f"📞 {tel}")
    note = _e(data.get('note'), 300)
    if note:
        righe.append(f"{'⚠️ <b>NOTE</b>:' if _nota_delicata(note) else '📝'} <i>{note}</i>")
    if not da_ospite and data.get('operatore'):
        righe.append(f"<i>da {_e(data.get('operatore'), 40)}</i>")
    return '\n'.join(righe)


# ── Ordini ristorazione ────────────────────────────────────────────────────

def _label_giorno(data_iso):
    try:
        target = datetime.strptime(data_iso, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return data_iso or ''
    oggi = datetime.now(ZoneInfo('Europe/Rome')).date()
    if target == oggi:
        return 'oggi'
    if target == oggi + timedelta(days=1):
        return 'domani'
    return target.strftime('%d/%m')


def _famiglie_mancanti(db, target_date, tipo):
    altro = 'cena' if tipo == 'pranzo' else 'pranzo'
    famiglie = [d.to_dict() | {'id': d.id} for d in db.collection('famiglie_ristorazione').stream()]

    def _ids(t):
        return {(o.to_dict() or {}).get('famiglia_id')
                for o in db.collection('ordini_ristorazione').where('data', '==', target_date).where('tipo', '==', t).stream()}
    correnti, altri = _ids(tipo), _ids(altro)
    mancanti = []
    for f in famiglie:
        checkin, checkout = f.get('checkin'), f.get('checkout')
        if checkin and checkin > target_date:
            continue
        if checkout and checkout <= target_date:
            continue
        if checkin == target_date and ((f.get('ora_arrivo') == 'dopo_pranzo' and tipo == 'pranzo') or f.get('ora_arrivo') == 'sera'):
            continue
        if f.get('trattamento') == 'MP':
            if f['id'] not in correnti and f['id'] not in altri:
                mancanti.append(f)
        elif f['id'] not in correnti:
            mancanti.append(f)
    return mancanti


def _famiglie_senza_ordine(db, target_date, tipo):
    return len(_famiglie_mancanti(db, target_date, tipo))


ALLERGIE = ('glutine', 'celiac', 'lattosio', 'allerg', 'intolleran', 'arachid', 'noci', 'frutta a guscio',
            'uova', 'pesce', 'crostacei', 'molluschi', 'soia', 'sesamo', 'sedano', 'senape', 'solfiti', 'vegan', 'vegetarian')


def _nota_delicata(note):
    n = (note or '').lower()
    return any(k in n for k in ALLERGIE)


def _righe_piatti(piatti, note=''):
    out = []
    for r in (piatti or [])[:25]:
        if isinstance(r, dict) and r.get('piatto'):
            out.append(f"• {_e(r.get('quantita') or 1, 4)}× {_e(r.get('piatto'), 60)}")
    if note:
        out.append(f"{'⚠️ <b>ALLERGIE/NOTE</b>:' if _nota_delicata(note) else '📝'} <i>{_e(note, 200)}</i>")
    return ('\n' + '\n'.join(out)) if out else ''


def _testo_ordine(db, famiglia, tipo, giorno, piatti=None, note='', unita=''):
    pasto = {'pranzo': 'Pranzo', 'cena': 'Cena'}.get(tipo, tipo or 'Pasto')
    dettaglio = _righe_piatti(piatti, note)
    intest = f"🍽️ <b>Nuovo ordine: {_e(famiglia, 120)}</b>" + (f" · {_e(unita, 40)}" if unita else '')
    if not giorno:
        return f"{intest}\n{_e(pasto, 20)} — nuovo ordine ricevuto{dettaglio}"
    mancanti = _famiglie_senza_ordine(db, giorno, tipo)
    quando = _label_giorno(giorno)
    if mancanti == 0:
        riga = f"{pasto} di {quando} — tutte le famiglie hanno ordinato ✓"
    else:
        riga = f"{pasto} di {quando} — mancano ancora {mancanti} famigli{'a' if mancanti == 1 else 'e'} all'appello"
    return f"{intest}\n{_e(riga, 200)}{dettaglio}"


def _notifica_ordine(db, doc_id, famiglia, tipo, giorno, piatti=None, note='', unita=''):
    inviati = _invia(['ristorazione'], _testo_ordine(db, famiglia or 'Ospite sconosciuto', tipo, giorno, piatti, note, unita))
    if doc_id:
        try:
            db.collection('ordini_ristorazione').document(doc_id).update({'notified': True})
        except Exception as ex:
            print(f'Errore marcatura notified per {doc_id}: {ex}')
    return inviati


def _ordini_pendenti(dry_run=False):
    """Rete di sicurezza: manda al gruppo Ristorazione gli ordini con notified=false
    (es. scritti dalla vecchia pagina Ristorazione, che non chiama il bot).
    Solo ordini per oggi o per giorni futuri: quelli di date passate vengono
    segnati come notificati senza inviare nulla (storico mai marcato)."""
    db = firestore.client()
    oggi = datetime.now(TZ).date().isoformat()
    pendenti = list(db.collection('ordini_ristorazione').where('notified', '==', False).limit(200).stream())
    attuali = [d for d in pendenti if str((d.to_dict() or {}).get('data') or '') >= oggi]
    vecchi = [d for d in pendenti if d not in attuali]
    if dry_run:
        return {'pendenti': len(attuali), 'vecchi_da_archiviare': len(vecchi)}
    for d in vecchi:
        try:
            d.reference.update({'notified': True})
        except Exception as ex:
            print(f'Errore archiviazione {d.id}: {ex}')
    inviati = 0
    for d in attuali[:20]:
        o = d.to_dict() or {}
        inviati += _notifica_ordine(db, d.id, o.get('famiglia_nome'), o.get('tipo'), o.get('data'), o.get('piatti'), o.get('note'), o.get('unita'))
    return {'pendenti': len(attuali), 'inviati': inviati, 'vecchi_archiviati': len(vecchi)}


# ── Eventi programmati (Cloud Scheduler) ───────────────────────────────────

CRON_EVENTI = ('promemoria_ticket', 'riepilogo_mattina', 'ordini_pendenti',
               'risto_sollecito', 'risto_riepilogo', 'risto_domani')
TZ = ZoneInfo('Europe/Rome')

# Ogni quante ore ripetere il promemoria di un ticket ancora aperto, per priorità.
# Il primo promemoria arriva dopo lo stesso intervallo dalla creazione.
PROMEMORIA_ORE = {'alta': 2, 'normale': 24, 'bassa': 72}
PROMEMORIA_DALLE, PROMEMORIA_ALLE = 8, 21   # niente messaggi di notte
PROMEMORIA_MAX_PER_GIRO = 8                 # oltre, un solo messaggio riassuntivo


def _cron_autorizzato(data):
    atteso = os.environ.get('CRON_TOKEN', '').strip()
    if not atteso:
        return False
    return hmac.compare_digest(str(data.get('_cron_token') or ''), atteso)


def _eta_leggibile(delta):
    ore = int(delta.total_seconds() // 3600)
    if ore < 1:
        return 'meno di 1 ora'
    if ore < 48:
        return f'{ore} ore'
    return f'{ore // 24} giorni'


def _promemoria_ticket(dry_run=False):
    """Ricorda al gruppo Manutenzione i ticket ancora aperti da troppo tempo.
    Un messaggio per ticket (con il pulsante 'Segna come risolto'); dopo averlo
    mandato segna `ultimo_promemoria` sul ticket, cosi' il giro successivo
    aspetta di nuovo l'intervallo completo."""
    adesso = datetime.now(timezone.utc)
    if not dry_run and not (PROMEMORIA_DALLE <= datetime.now(TZ).hour < PROMEMORIA_ALLE):
        return {'inviati': 0, 'motivo': 'fuori_orario'}
    db = firestore.client()
    scaduti = []
    diagnosi = []  # solo per dry_run: tutti i ticket aperti e perche' (non) sono scaduti
    for snap in db.collection('maintenance_tickets').where('status', '==', False).stream():
        t = snap.to_dict() or {}
        creato = t.get('created_at')
        if not isinstance(creato, datetime):
            diagnosi.append(f"{snap.id}: {t.get('housing_unit')} — SALTATO, created_at non valido ({type(creato).__name__})")
            continue  # serverTimestamp non ancora risolto o dato anomalo
        if creato.tzinfo is None:
            creato = creato.replace(tzinfo=timezone.utc)
        prio = t.get('priority') if t.get('priority') in PROMEMORIA_ORE else 'normale'
        ultimo = t.get('ultimo_promemoria')
        if isinstance(ultimo, datetime):
            if ultimo.tzinfo is None:
                ultimo = ultimo.replace(tzinfo=timezone.utc)
        else:
            ultimo = None
        riferimento = max(creato, ultimo) if ultimo else creato
        scade = adesso - riferimento >= timedelta(hours=PROMEMORIA_ORE[prio])
        diagnosi.append(f"{snap.id}: {t.get('housing_unit')} · {prio} · aperto da {_eta_leggibile(adesso - creato)}"
                        f" · soglia {PROMEMORIA_ORE[prio]}h · {'DA RICORDARE' if scade else 'non ancora'}")
        if scade:
            scaduti.append((prio != 'alta', creato, snap, t, prio, adesso - creato))
    scaduti.sort(key=lambda x: (x[0], x[1]))  # urgenti prima, poi i piu' vecchi

    inviati = 0
    anteprima = []
    for _, _, snap, t, prio, eta in scaduti[:PROMEMORIA_MAX_PER_GIRO]:
        intestazione = '🚨 <b>Ticket URGENTE ancora aperto</b>' if prio == 'alta' else '⏰ <b>Ticket ancora aperto</b>'
        testo = (f"{intestazione} da {_eta_leggibile(eta)}\n\n"
                 f"🏠 <b>Alloggio:</b> {_e(t.get('housing_unit'), 80) or '—'}\n"
                 f"🏷️ <b>Categoria:</b> {_e(t.get('category'), 80) or '—'}\n\n"
                 f"📝 {_e(t.get('issue_description'), 400) or '—'}")
        if dry_run:
            anteprima.append(testo)
            continue
        tastiera = [[{'text': '✅ Segna come risolto', 'callback_data': f'risolto:{snap.id}'}]]
        if _invia(['manutenzione'], testo, tastiera=tastiera):
            inviati += 1
            try:
                snap.reference.update({'ultimo_promemoria': firestore.SERVER_TIMESTAMP})
            except Exception as ex:
                print(f'Marcatura ultimo_promemoria fallita per {snap.id}: {ex}')
    resto = len(scaduti) - PROMEMORIA_MAX_PER_GIRO
    if resto > 0:
        if dry_run:
            anteprima.append(f'… e altri {resto}')
        else:
            _invia(['manutenzione'], f'⏰ Altri <b>{resto}</b> ticket aperti da troppo tempo: apri {SITE_URL}/manutenzione/')
            for _, _, snap, _, _, _ in scaduti[PROMEMORIA_MAX_PER_GIRO:]:
                try:
                    snap.reference.update({'ultimo_promemoria': firestore.SERVER_TIMESTAMP})
                except Exception as ex:
                    print(f'Marcatura ultimo_promemoria fallita per {snap.id}: {ex}')
    return {'inviati': inviati, 'scaduti': len(scaduti), **({'anteprima': anteprima, 'ticket_aperti': diagnosi} if dry_run else {})}


def _persone_pren(p):
    try:
        n = sum(int(p.get(k) or 0) for k in ('adulti', 'bambini_0_2', 'bambini_3_4', 'bambini_5_9', 'bambini_10_17'))
    except (TypeError, ValueError):
        n = 0
    return n if n > 0 else len([o for o in (p.get('ospiti') or []) if o])


def _riepilogo_mattina(dry_run=False, forza=False):
    """Riepilogo del giorno per la Reception: arrivi, partenze, alloggi non
    ancora pronti per chi arriva, ticket urgenti aperti."""
    adesso = datetime.now(TZ)
    oggi = adesso.date().isoformat()
    db = firestore.client()

    ref_stato = db.collection('impostazioni').document('telegram_cron')
    if not dry_run and not forza:
        snap = ref_stato.get()
        if snap.exists and (snap.to_dict() or {}).get('riepilogo_mattina') == oggi:
            return {'inviati': 0, 'motivo': 'gia_inviato_oggi'}

    alloggi = {d.id: (d.to_dict() or {}) for d in db.collection('alloggi').stream()}
    arrivi = [d.to_dict() or {} for d in db.collection('prenotazioni').where('checkin', '==', oggi).stream()]
    partenze = [d.to_dict() or {} for d in db.collection('prenotazioni').where('checkout', '==', oggi).stream()]
    urgenti = [d.to_dict() or {} for d in db.collection('maintenance_tickets')
               .where('status', '==', False).where('priority', '==', 'alta').stream()]

    def chiave(p):
        return (str(p.get('alloggio_nome') or '~').lower(), str(p.get('nome') or '').lower())
    arrivi.sort(key=chiave)
    partenze.sort(key=chiave)

    MAX = 25
    righe = [f"☀️ <b>Buongiorno! Riepilogo di oggi</b> · {adesso.strftime('%d/%m/%Y')}"]

    righe.append(f"\n🛬 <b>Arrivi ({len(arrivi)})</b>")
    if not arrivi:
        righe.append('Nessun arrivo previsto.')
    non_pronti = 0
    for p in arrivi[:MAX]:
        stato = (alloggi.get(p.get('alloggio_id')) or {}).get('stato')
        pers = _persone_pren(p)
        riga = f"• {_e(p.get('alloggio_nome'), 40) or 'Alloggio da assegnare'} — {_e(p.get('nome'), 50) or '—'}"
        if pers:
            riga += f" ({pers} pers.)"
        if p.get('checkin_fatto'):
            riga += ' ✔️ già arrivato'
        elif p.get('alloggio_id') and stato and stato != 'pronta':
            non_pronti += 1
            riga += f" {EMOJI_STATO.get(stato, '⚠️')} {_e(LABEL_STATO.get(stato, stato), 30)}"
        righe.append(riga)
    if len(arrivi) > MAX:
        righe.append(f'… e altri {len(arrivi) - MAX}')
    if non_pronti:
        righe.append(f"⚠️ <i>{non_pronti} alloggio/i di chi arriva non ancora pronti.</i>")

    righe.append(f"\n🛫 <b>Partenze ({len(partenze)})</b>")
    if not partenze:
        righe.append('Nessuna partenza prevista.')
    for p in partenze[:MAX]:
        riga = f"• {_e(p.get('alloggio_nome'), 40) or '—'} — {_e(p.get('nome'), 50) or '—'}"
        if p.get('checkout_fatto'):
            riga += ' ✔️ già partito'
        righe.append(riga)
    if len(partenze) > MAX:
        righe.append(f'… e altre {len(partenze) - MAX}')

    if urgenti:
        righe.append(f"\n🚨 <b>Ticket urgenti aperti ({len(urgenti)})</b>")
        for t in urgenti[:10]:
            righe.append(f"• {_e(t.get('housing_unit'), 40) or '—'} — {_e(t.get('category'), 40) or '—'}: {_e(t.get('issue_description'), 80)}")
        if len(urgenti) > 10:
            righe.append(f'… e altri {len(urgenti) - 10}')

    testo = '\n'.join(righe)
    if dry_run:
        return {'inviati': 0, 'anteprima': testo}
    inviati = _invia(['reception'], testo)
    if inviati:
        ref_stato.set({'riepilogo_mattina': oggi}, merge=True)
    return {'inviati': inviati}


def _gia_inviato(db, chiave, oggi, dry_run, forza):
    """Una sola volta al giorno per chiave (doc `impostazioni/telegram_cron`)."""
    ref = db.collection('impostazioni').document('telegram_cron')
    if not dry_run and not forza:
        snap = ref.get()
        if snap.exists and (snap.to_dict() or {}).get(chiave) == oggi:
            return ref, True
    return ref, False


def _risto_sollecito(dry_run=False, forza=False):
    """Poco prima delle 8:30 (chiusura ordini ospiti): chi non ha ancora ordinato oggi."""
    oggi = datetime.now(TZ).date().isoformat()
    db = firestore.client()
    ref, fatto = _gia_inviato(db, 'risto_sollecito', oggi, dry_run, forza)
    if fatto:
        return {'inviati': 0, 'motivo': 'gia_inviato_oggi'}
    righe, totale = ['⏰ <b>Ordini ancora aperti: si chiude alle 8:30</b>'], 0
    for tipo, etichetta in (('pranzo', 'Pranzo'), ('cena', 'Cena')):
        mancanti = sorted(_famiglie_mancanti(db, oggi, tipo), key=lambda f: str(f.get('nome') or '').lower())
        totale += len(mancanti)
        if not mancanti:
            continue
        righe.append(f"\n<b>{etichetta}</b> — mancano {len(mancanti)}:")
        for f in mancanti[:20]:
            righe.append(f"• {_e(f.get('nome'), 60) or '—'}" + (f" · {_e(f.get('unita'), 30)}" if f.get('unita') else ''))
        if len(mancanti) > 20:
            righe.append(f'… e altre {len(mancanti) - 20}')
    if not totale:
        return {'inviati': 0, 'motivo': 'tutti_hanno_ordinato'}
    righe.append("\n<i>Dopo le 8:30 solo lo staff può sbloccare l'ordine dalla Ristorazione.</i>")
    testo = '\n'.join(righe)
    if dry_run:
        return {'inviati': 0, 'anteprima': testo}
    inviati = _invia(['ristorazione'], testo)
    if inviati:
        ref.set({'risto_sollecito': oggi}, merge=True)
    return {'inviati': inviati}


def _corpo_riepilogo(db, giorno, tipo):
    """(testo senza intestazione, n. ordini) delle quantita' ordinate per `giorno`/`tipo`."""
    ordini = [d.to_dict() or {} for d in db.collection('ordini_ristorazione')
              .where('data', '==', giorno).where('tipo', '==', tipo).stream()]
    per_cat, note, allergie = {}, [], []
    for o in ordini:
        for r in (o.get('piatti') or []):
            if isinstance(r, dict) and r.get('piatto'):
                cat = str(r.get('categoria') or 'Altro')
                per_cat.setdefault(cat, {})
                per_cat[cat][r['piatto']] = per_cat[cat].get(r['piatto'], 0) + int(r.get('quantita') or 0)
        if o.get('note'):
            riga = f"• {_e(o.get('famiglia_nome'), 50)}: {_e(o.get('note'), 150)}"
            (allergie if _nota_delicata(o.get('note')) else note).append(riga)
    righe = [f"{len(ordini)} ordini ricevuti"]
    for cat in sorted(per_cat, key=lambda c: (c == 'Menu Bambini', c)):
        righe.append(f"\n<b>{_e(cat, 40)}</b>")
        for piatto, q in sorted(per_cat[cat].items(), key=lambda x: (-x[1], x[0])):
            righe.append(f"• {q}× {_e(piatto, 60)}")
    if allergie:
        righe.append('\n⚠️ <b>Allergie / intolleranze</b>')
        righe.extend(allergie[:15])
    if note:
        righe.append('\n📝 <b>Note</b>')
        righe.extend(note[:15])
    return '\n'.join(righe), len(ordini)


def _risto_riepilogo(tipo, dry_run=False, forza=False, domani=False):
    """Riepilogo quantita' da preparare: pasto di oggi (pranzo/cena) oppure, con
    domani=True, gli ordini gia' arrivati per domani (pranzo e cena)."""
    if not domani and tipo not in ('pranzo', 'cena'):
        return {'inviati': 0, 'motivo': 'pasto_non_valido'}
    adesso = datetime.now(TZ)
    oggi = adesso.date().isoformat()
    giorno = (adesso.date() + timedelta(days=1)).isoformat() if domani else oggi
    db = firestore.client()
    chiave = 'risto_domani' if domani else f'risto_riepilogo_{tipo}'
    ref, fatto = _gia_inviato(db, chiave, oggi, dry_run, forza)
    if fatto:
        return {'inviati': 0, 'motivo': 'gia_inviato_oggi'}
    tipi = ('pranzo', 'cena') if domani else (tipo,)
    righe = [f"📅 <b>Ordini per domani</b> · {_label_giorno(giorno)} {giorno[8:]}/{giorno[5:7]}"] if domani else \
            [f"{'☀️' if tipo == 'pranzo' else '🌙'} <b>{'Pranzo' if tipo == 'pranzo' else 'Cena'} di oggi — riepilogo</b>"]
    for t in tipi:
        corpo, n = _corpo_riepilogo(db, giorno, t)
        mancanti = _famiglie_mancanti(db, giorno, t)
        if domani:
            righe.append(f"\n{'☀️ <b>Pranzo</b>' if t == 'pranzo' else '🌙 <b>Cena</b>'}")
        righe.append(corpo if n else 'Nessun ordine ricevuto.')
        if mancanti:
            righe.append(f"\n⚠️ <i>{len(mancanti)} {'famiglia non ha' if len(mancanti) == 1 else 'famiglie non hanno'} ancora ordinato"
                         + (f": {', '.join(_e(f.get('nome'), 30) for f in mancanti[:8])}" if domani else '.') + '</i>')
    testo = '\n'.join(righe)
    if dry_run:
        return {'inviati': 0, 'anteprima': testo}
    inviati = _invia(['ristorazione'], testo)
    if inviati:
        ref.set({chiave: oggi}, merge=True)
    return {'inviati': inviati}


# ── Autorizzazione chiamate ────────────────────────────────────────────────
# Un endpoint pubblico che manda notifiche reali non può accettare chiunque.
# Accetta: (a) l'ID token Firebase di un operatore (claim `operatore`, header
# Authorization: Bearer ...) — è come chiama la Hub dal browser; (b) il segreto
# condiviso tra funzioni (header X-Internal-Token = env INTERNAL_TOKEN) — è come
# chiamano le altre Cloud Function (area-ospite, checkin-online).
def _autorizzato(request):
    import hmac
    from firebase_admin import auth as fb_auth
    interno = os.environ.get('INTERNAL_TOKEN', '').strip()
    t = request.headers.get('X-Internal-Token', '')
    if interno and t and hmac.compare_digest(t, interno):
        return True
    h = request.headers.get('Authorization', '')
    if h.startswith('Bearer '):
        try:
            return bool(fb_auth.verify_id_token(h[7:].strip()).get('operatore'))
        except Exception as e:
            print(f'ID token non valido: {e}')
    return False


@functions_framework.http
def telegram_bot(request):
    origin = request.headers.get('Origin', '')
    if request.method == 'OPTIONS':
        return ('', 204, _cors(origin))
    if request.method != 'POST':
        return _json(origin, {'ok': False, 'errore': 'metodo non permesso'}, 405)

    data = request.get_json(force=True, silent=True) or {}

    secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
    if secret is not None:  # chiamata di Telegram
        if not WEBHOOK_SECRET or secret != WEBHOOK_SECRET:
            return ('', 403)
        msg = data.get('message') or data.get('channel_post') or {}
        try:
            if data.get('callback_query'):
                _callback(data['callback_query'])
            else:
                _comando(msg)
        except Exception as ex:
            print(f'Errore comando: {ex}')
        return ('', 200)  # sempre 200, altrimenti Telegram riprova all'infinito

    if data.get('evento') in CRON_EVENTI:
        if not _cron_autorizzato(data):
            return _json(origin, {'ok': False, 'errore': 'token_non_valido'}, 403)
        dry = bool(data.get('dry_run'))
        if data['evento'] == 'promemoria_ticket':
            res = _promemoria_ticket(dry)
        elif data['evento'] == 'risto_sollecito':
            res = _risto_sollecito(dry, bool(data.get('forza')))
        elif data['evento'] == 'risto_riepilogo':
            res = _risto_riepilogo(str(data.get('pasto') or ''), dry, bool(data.get('forza')))
        elif data['evento'] == 'risto_domani':
            res = _risto_riepilogo('', dry, bool(data.get('forza')), domani=True)
        elif data['evento'] == 'ordini_pendenti':
            res = _ordini_pendenti(dry)
        else:
            res = _riepilogo_mattina(dry, bool(data.get('forza')))
        return _json(origin, {'ok': True, **res})

    if data.get('evento') == 'feed_notifiche':
        if not _feed_autorizzato(request):
            return _json(origin, {'ok': False, 'errore': 'non_autorizzato'}, 401)
        return _json(origin, {'ok': True, **_feed_notifiche(data)})

    if not _autorizzato(request):
        return _json(origin, {'ok': False, 'errore': 'non_autorizzato'}, 401)

    if data.get('evento') == 'feed_chiave':   # l'app la riceve da sola dopo il login di un operatore
        chiave = os.environ.get('APP_FEED_KEY', '').strip()
        if not chiave:
            return _json(origin, {'ok': False, 'errore': 'non_configurata'}, 503)
        return _json(origin, {'ok': True, 'key': chiave})

    inviati = _evento(data)
    if inviati is None:
        return _json(origin, {'ok': False, 'errore': 'evento non valido'}, 400)
    return _json(origin, {'ok': True, 'inviati': inviati})
