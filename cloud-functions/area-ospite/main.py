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
        -> riepilogo sanificato della prenotazione (nome, telefono, alloggio
           — il numero dell'alloggio e' nascosto fino al giorno dopo il
           check-in, v. _alloggio_per_ospite: possono esserci cambi fino
           all'arrivo)
           + il conto (voci, totale, pagato, residuo da pagare — da
           prenotazione.conto.righe, scritto dal Calendario)
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
from firebase_admin import auth as fb_auth, firestore
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
    # Posti di ogni pulmino: un autista porta piu' prenotazioni nello stesso
    # orario finche' la somma delle persone non supera questo numero.
    'posti_pulmino': 8,
    # Usato solo se non ci sono autisti configurati: quanti pulmini
    # partono contemporaneamente (ognuno con 'posti_pulmino' posti).
    'max_corse_per_orario': 1,
}
SERVIZI_FOTO = ('home', 'navetta', 'ristorazione', 'animazione', 'info', 'assistenza')

MAX_TESTO = 120

# Una corsa ancora 'in attesa/confermata' ma con l'orario passato da piu' di
# questi minuti non conta piu' come attiva (l'autista si e' dimenticato di
# chiuderla): non blocca il cliente ne' occupa posti.
SCADENZA_CORSA_MINUTI = 60


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
        for k in ('passo_minuti', 'preavviso_minimo_minuti', 'preavviso_modifica_minuti', 'max_corse_per_orario', 'posti_pulmino'):
            try:
                v = int(d.get(k))
                if v >= (5 if k == 'passo_minuti' else 1 if k in ('max_corse_per_orario', 'posti_pulmino') else 0):
                    cfg[k] = v
            except (TypeError, ValueError):
                pass
        cfg['punti_ritiro'] = _punti_ritiro(d.get('punti_ritiro'))
    except Exception as e:
        print(f'Lettura impostazioni/navetta non riuscita: {e}')
    cfg.setdefault('punti_ritiro', [])
    # Ogni autista ha un pulmino da 'posti_pulmino' posti: i posti di un orario
    # si contano per autista. Senza autisti configurati vale un unico gruppo di
    # 'max_corse_per_orario' pulmini.
    cfg['autisti'] = [a['nome'] for a in _autisti_elenco(db, con_foto=False)]
    return cfg


def _punti_ritiro(grezzi):
    """Punti di raccolta dalle impostazioni: [{spiaggia, nome, indicazioni,
    lat, lng, link}]. 'posizione' puo' essere 'lat, lng', un link di Google
    Maps con le coordinate, oppure un qualsiasi link http(s)."""
    out = []
    for r in grezzi or []:
        if not isinstance(r, dict):
            continue
        nome, indic = _s(r.get('nome'), 120), _s(r.get('indicazioni'), 400)
        pos = _s(r.get('posizione'), 400)
        lat = lng = None
        m = re.search(r'(-?\d{1,2}\.\d{3,})\s*[,;]\s*(-?\d{1,3}\.\d{3,})', pos)
        if m and -90 <= float(m.group(1)) <= 90 and -180 <= float(m.group(2)) <= 180:
            lat, lng = float(m.group(1)), float(m.group(2))
        link = pos if re.match(r'https?://', pos, re.I) else ''
        if not (nome or indic or lat is not None or link):
            continue
        out.append({'spiaggia': _s(r.get('spiaggia'), 80), 'nome': nome, 'indicazioni': indic,
                    'lat': lat, 'lng': lng, 'link': link})
    return out


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


def _persone_prenotazione(p):
    """Persone totali della prenotazione (adulti + bambini); 0 se non note."""
    try:
        n = sum(int(p.get(k) or 0) for k in ('adulti', 'bambini_0_2', 'bambini_3_4', 'bambini_5_9', 'bambini_10_17'))
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        n = len([o for o in (p.get('ospiti') or []) if o])
    return n


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


def _autisti_elenco(db, con_foto=True):
    """Autisti configurati (collezione navetta_autisti, gestita dalla
    dashboard Navetta) — sono sempre tutti disponibili, nessuna gestione
    giorno per giorno. Ogni corsa deve avere un autista scelto dal cliente."""
    try:
        return [
            {'id': d.id, 'nome': _s((d.to_dict() or {}).get('nome')) or d.id,
             'foto': _s((d.to_dict() or {}).get('foto'), 300000) if con_foto else ''}
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
                'persone': _persone(x),
                'spiaggia_nome': _s(x.get('spiaggia_nome')),
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


def _alloggio_per_ospite(nome, checkin_iso, oggi_iso):
    """Nome alloggio mostrato all'ospite: senza il numero finale finché non è
    passato un giorno dall'arrivo (checkin) — in caso di cambi alloggio
    dell'ultimo momento. Dal giorno dopo il check-in si vede il nome completo.
    Usato SOLO per quanto l'ospite legge a schermo: le azioni operative
    (es. navetta) usano sempre il nome reale letto da Firestore."""
    if not nome or not checkin_iso or oggi_iso > checkin_iso:
        return nome
    return re.sub(r'\s+\S+$', '', nome)


def _conto_prenotazione(p):
    """Riepilogo del conto per l'ospite (stesso calcolo di calcolaSaldoConto
    in calendario/index.html): voci non-acconto fanno il totale del
    soggiorno; le voci pagate e gli acconti riducono il residuo da pagare.
    Il campo `conto.righe` vive sulla prenotazione stessa, scritto dal
    Calendario — qui solo letto e sanificato, mai modificato."""
    righe = (p.get('conto') or {}).get('righe') or []
    totale = pagato_normale = acconti = 0.0
    voci = []
    for r in righe:
        if not isinstance(r, dict):
            continue
        try:
            importo = round(float(r.get('importo') or 0), 2)
        except (TypeError, ValueError):
            importo = 0.0
        acconto = bool(r.get('acconto'))
        pagato = bool(r.get('pagato'))
        if acconto:
            acconti += abs(importo)
        else:
            totale += importo
            if pagato:
                pagato_normale += importo
        voci.append({'label': _s(r.get('label'), 160), 'importo': importo, 'pagato': pagato, 'acconto': acconto})
    return {
        'voci': voci,
        'totale': round(totale, 2),
        'pagato': round(pagato_normale + acconti, 2),
        'da_pagare': round(totale - pagato_normale - acconti, 2),
    }


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


def _corse_attive_oggi(db, transaction=None):
    """[(id, dict)] delle corse ancora attive oggi, di tutti gli ospiti."""
    q = db.collection('navetta_prenotazioni').where('data', '==', _oggi_iso())
    docs = q.stream(transaction=transaction) if transaction is not None else q.stream()
    return [(d.id, d.to_dict() or {}) for d in docs
            if (d.to_dict() or {}).get('stato') in ('in_attesa', 'accettata') and not _scaduta(d.to_dict() or {})]


def _scaduta(x):
    """Corsa di oggi con l'orario passato da oltre SCADENZA_CORSA_MINUTI."""
    try:
        return _minuti_da_ora(x.get('orario') or '23:59') < -SCADENZA_CORSA_MINUTI
    except Exception:
        return False


def _persone(x):
    """Persone di una corsa (le vecchie corse senza il campo valgono 1)."""
    try:
        return max(1, int(x.get('persone') or 1))
    except (TypeError, ValueError):
        return 1


def _occupazione(corse_ora):
    """({autista normalizzato: persone}, persone senza autista) di un orario."""
    per_aut, senza = {}, 0
    for x in corse_ora:
        a = _norm_nome(x.get('autista_nome'))
        if a:
            per_aut[a] = per_aut.get(a, 0) + _persone(x)
        else:
            senza += _persone(x)
    return per_aut, senza


def _liberi_autista(corse_ora, cfg, autista):
    """Posti ancora liberi sul pulmino di quell'autista a quell'orario. Le corse
    ancora senza autista tolgono posti a tutti (per prudenza). Senza autisti
    configurati c'e' un unico gruppo di pulmini."""
    per_aut, senza = _occupazione(corse_ora)
    if not cfg['autisti']:
        return cfg['posti_pulmino'] * cfg['max_corse_per_orario'] - sum(per_aut.values()) - senza
    return cfg['posti_pulmino'] - per_aut.get(_norm_nome(autista), 0) - senza


def _max_liberi(corse_ora, cfg):
    """Il maggior numero di posti liberi su un singolo pulmino a quell'orario."""
    if not cfg['autisti']:
        return _liberi_autista(corse_ora, cfg, '')
    return max(_liberi_autista(corse_ora, cfg, a) for a in cfg['autisti'])


def _orari_occupati(attive, cfg):
    """Orari in cui nessun pulmino ha piu' un posto libero (uguale per tutti
    gli ospiti: e' l'unica informazione sugli altri che viene condivisa)."""
    per_ora = {}
    for _id, x in attive:
        if x.get('orario'):
            per_ora.setdefault(x['orario'], []).append(x)
    return sorted(o for o, corse in per_ora.items() if _max_liberi(corse, cfg) <= 0)


def _puo_ospitare(corse_ora, cfg, autista, spiaggia, persone):
    """Il pulmino di quell'autista puo' prendere questo gruppo a quell'orario?
    Servono i posti e, se ha gia' altre prenotazioni a quell'ora, devono
    andare alla STESSA spiaggia (un pulmino fa un solo giro). Una corsa senza
    spiaggia indicata (vecchie richieste) non pone vincoli."""
    if _liberi_autista(corse_ora, cfg, autista) < persone:
        return False
    if cfg['autisti']:
        a, sp = _norm_nome(autista), _norm_nome(spiaggia)
        for x in corse_ora:
            xs = _norm_nome(x.get('spiaggia_nome'))
            if sp and xs and xs != sp and _norm_nome(x.get('autista_nome')) == a:
                return False
    return True


def _posti_occupati(attive, cfg):
    """{orario: {nome autista: {'n': persone gia' a bordo, 'spiagge': [...]}}}
    (la chiave '' sono le corse senza autista): serve al cliente per sapere se
    l'autista scelto ha ancora posto per il suo gruppo e va alla sua stessa
    spiaggia. Nessun dato personale."""
    out = {}
    for _id, x in attive:
        o = x.get('orario')
        if not o:
            continue
        riga = out.setdefault(o, {}).setdefault(_s(x.get('autista_nome')), {'n': 0, 'spiagge': []})
        riga['n'] += _persone(x)
        sp = _s(x.get('spiaggia_nome'))
        if sp and sp not in riga['spiagge']:
            riga['spiagge'].append(sp)
    return out


def _stessa_persona(x, pren_id, tel):
    """La corsa x e' dello stesso cliente? Per prenotazione (prenId); le corse
    create dallo staff non hanno prenId e si riconoscono dal telefono. Il solo
    nome non basta: troppi omonimi / cognomi uguali."""
    if pren_id and x.get('prenId') == pren_id:
        return True
    return bool(tel) and _norm_tel(x.get('telefono')) == tel and (not pren_id or not x.get('prenId'))


def _verifica_slot(attive, cfg, pren_id, orario, nome='', telefono='', escludi_id=None, autista='', persone=1, spiaggia='', totale=None):
    """None se l'orario e' libero per questo cliente e per questo gruppo,
    altrimenti il codice d'errore: 'corsa_duplicata' (il cliente ha gia' una
    corsa a quell'ora); 'persone_esaurite' (con questa corsa le persone in
    corse attive supererebbero quelle della prenotazione, `totale`);
    'orario_occupato' (nessun pulmino ha piu' posti); 'autista_occupato'
    (l'autista scelto non puo' prendere il gruppo, per posti o perche' va a
    un'altra spiaggia, ma un collega si); 'posti_insufficienti' (nessun
    autista puo' prendere il gruppo)."""
    t = _norm_tel(telefono)
    altre = [x for i, x in attive if i != escludi_id]
    sue = [x for x in altre if _stessa_persona(x, pren_id, t)]
    if any(x.get('orario') == orario for x in sue):
        return 'corsa_duplicata'
    if totale and pren_id and sum(_persone(x) for x in sue) + persone > totale:
        return 'persone_esaurite'
    stessa_ora = [x for x in altre if x.get('orario') == orario]
    if _puo_ospitare(stessa_ora, cfg, autista, spiaggia, persone):
        return None
    if any(_puo_ospitare(stessa_ora, cfg, a, spiaggia, persone) for a in cfg['autisti']):
        return 'autista_occupato'
    return 'orario_occupato' if _max_liberi(stessa_ora, cfg) <= 0 else 'posti_insufficienti'


@firestore.transactional
def _scrivi_se_libero(transaction, db, cfg, ref, scrittura, pren_id, orario, nome, telefono, escludi_id=None, autista='', persone=1, spiaggia='', totale=None):
    """Controllo e scrittura nella stessa transazione: due richieste
    contemporanee per l'ultimo posto di un orario non passano entrambe."""
    err = _verifica_slot(_corse_attive_oggi(db, transaction), cfg, pren_id, orario, nome, telefono, escludi_id, autista, persone, spiaggia, totale)
    if err:
        return err
    if escludi_id:
        transaction.update(ref, scrittura)
    else:
        transaction.set(ref, scrittura)
    return None


# ── azioni ─────────────────────────────────────────────────────────────────

def _azione_carica(db, origin, data):
    pren_ref, p = _risolvi_token(db, data.get('token'))
    if not p:
        return _json(origin, {'ok': False, 'errore': 'link_non_valido'}, 404)
    cfg = _cfg_navetta(db)
    attive = _corse_attive_oggi(db)

    return _json(origin, {
        'ok': True,
        'prenotazione': {
            'nome':          _s(p.get('nome')),
            'nome_proprio':  _nome_proprio(p),
            'telefono':      _s(p.get('tel')),
            'persone_totali': _persone_prenotazione(p),
            'alloggio_nome': _alloggio_per_ospite(_s(p.get('alloggio_nome')), _s(p.get('checkin'), 10), _oggi_iso()),
            'checkin':       _s(p.get('checkin')),
            'checkout':      _s(p.get('checkout')),
        },
        'conto': _conto_prenotazione(p),
        'spiaggia': _spiaggia_assegnata(db, pren_ref.id),
        'spiagge': _spiagge_disponibili(db),
        'autisti': _autisti_elenco(db),
        'ristorazione': _ristorazione_disponibile(db, pren_ref.id),
        'navetta_corse': _navetta_corse_cliente(db, pren_ref.id),
        'orari_occupati': _orari_occupati(attive, cfg),
        'posti_occupati': _posti_occupati(attive, cfg),
        'posti_pulmino': cfg['posti_pulmino'],
        'max_corse_per_orario': cfg['max_corse_per_orario'],
        'punti_ritiro': cfg['punti_ritiro'],
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
    cfg_n = _cfg_navetta(db)
    attive = _corse_attive_oggi(db)
    return _json(origin, {
        'ok': True,
        'navetta_corse': _navetta_corse_cliente(db, pren_ref.id),
        'orari_occupati': _orari_occupati(attive, cfg_n),
        'posti_occupati': _posti_occupati(attive, cfg_n),
        'oggi': _oggi_iso(),
    })


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
    # Nome alloggio reale (mai quello eventualmente mascherato lato ospite):
    # l'autista deve sapere l'unita' esatta a cui riportare il cliente.
    alloggio_nome = _s(p.get('alloggio_nome'))
    # La spiaggia e' obbligatoria: l'autista deve sapere dove andare. Se il
    # Calendario ha gia' assegnato l'ombrellone si usa quella.
    assegnata = _spiaggia_assegnata(db, pren_ref.id)
    spiaggia_nome = _s(data.get('spiaggia_nome')) or (assegnata or {}).get('spiaggia_nome') or ''
    if not spiaggia_nome:
        return _json(origin, {'ok': False, 'errore': 'spiaggia_obbligatoria'}, 400)
    try:
        persone = int(data.get('persone'))
    except (TypeError, ValueError):
        persone = 0
    if persone < 1 or persone > cfg['posti_pulmino']:
        return _json(origin, {'ok': False, 'errore': 'persone_non_valide'}, 400)
    # Ogni corsa ha un autista preciso, scelto dal cliente tra quelli configurati
    # (nessuna assegnazione 'a caso'). Se non e' stato configurato nessun autista
    # la corsa resta senza.
    autisti = [a['nome'] for a in _autisti_elenco(db)]
    autista_nome = ''
    if autisti:
        scelto = _norm_nome(_s(data.get('autista_nome')))
        autista_nome = next((n for n in autisti if _norm_nome(n) == scelto), '') if scelto else ''
        if not autista_nome:
            return _json(origin, {'ok': False, 'errore': 'autista_obbligatorio'}, 400)
    if not nome or not telefono:
        return _json(origin, {'ok': False, 'errore': 'dati_incompleti'}, 400)

    doc = {
        'prenId':        pren_ref.id,
        'alloggio_nome': alloggio_nome,
        'nome':          nome,
        'telefono':      telefono,
        'spiaggia_nome': spiaggia_nome,
        'persone':       persone,
        'data':          _oggi_iso(),
        'orario':        orario,
        # La richiesta e' subito confermata: l'autista non deve accettarla.
        'stato':         'accettata',
        'accettata_il':  _now_iso(),
        'autista_nome':  autista_nome or None,
        'creato_il':     _now_iso(),
    }
    ref = db.collection('navetta_prenotazioni').document()
    err = _scrivi_se_libero(db.transaction(), db, cfg, ref, doc, pren_ref.id, orario, nome, telefono, autista=autista_nome, persone=persone, spiaggia=spiaggia_nome, totale=_persone_prenotazione(p))
    if err:
        return _json(origin, {'ok': False, 'errore': err}, 409)
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
    err = _scrivi_se_libero(db.transaction(), db, cfg, ref, {
        'orario': orario,
        'orario_precedente': c.get('orario') or '',
        'orario_modificato_il': _now_iso(),
        'aggiornato_il': _now_iso(),
    }, pren_ref.id, orario, c.get('nome'), c.get('telefono'), escludi_id=snap.id, autista=_s(c.get('autista_nome')), persone=_persone(c), spiaggia=_s(c.get('spiaggia_nome')), totale=_persone_prenotazione(p))
    if err:
        return _json(origin, {'ok': False, 'errore': err}, 409)
    return _json(origin, {'ok': True, 'id': snap.id})


def _azione_navetta_annulla(db, origin, data):
    """L'ospite annulla una sua corsa di oggi (stesso preavviso del cambio
    orario): cosi' puo' correggere un errore e prenotare di nuovo."""
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
    if _minuti_da_ora(c.get('orario') or '00:00') < cfg['preavviso_modifica_minuti']:
        return _json(origin, {'ok': False, 'errore': 'troppo_tardi'}, 409)
    ref.update({'stato': 'annullata', 'annullata_il': _now_iso(), 'annullata_da': 'ospite', 'aggiornato_il': _now_iso()})
    return _json(origin, {'ok': True, 'id': snap.id})


# ── azioni dello staff (dashboard Navetta) ─────────────────────────────────
# Stesse regole della prenotazione dell'ospite (posti, spiaggia, orari validi,
# transazione): la dashboard non scrive piu' direttamente le corse. Autenticate
# col token di Firebase Auth del dispositivo (lo stesso che le regole Firestore
# richiedono gia' per scrivere).

def _staff_autenticato(data):
    try:
        return bool(fb_auth.verify_id_token(_s(data.get('id_token'), 4000)))
    except Exception as e:
        print(f'Token staff non valido: {e}')
        return False


def _orario_staff_valido(orario, cfg):
    """Orario di una fascia/passo configurati; lo staff puo' prenotare anche con
    poco preavviso, ma non nel passato."""
    return bool(re.fullmatch(r'[0-2]\d:[0-5]\d', orario or '')) and orario in _slot_validi(cfg) and _minuti_da_ora(orario) >= -10


def _campi_corsa_staff(db, cfg, data):
    """Valida e normalizza i campi di una corsa dello staff. Ritorna
    (campi, errore)."""
    nome, telefono = _s(data.get('nome')), _s(data.get('telefono'))
    if not nome or not telefono:
        return None, 'dati_incompleti'
    spiaggia = _s(data.get('spiaggia_nome'))
    if not spiaggia:
        return None, 'spiaggia_obbligatoria'
    try:
        persone = int(data.get('persone'))
    except (TypeError, ValueError):
        persone = 0
    if persone < 1 or persone > cfg['posti_pulmino']:
        return None, 'persone_non_valide'
    autista = ''
    if cfg['autisti']:
        scelto = _norm_nome(_s(data.get('autista_nome')))
        autista = next((n for n in cfg['autisti'] if _norm_nome(n) == scelto), '') if scelto else ''
        if not autista:
            return None, 'autista_obbligatorio'
    return {'nome': nome, 'telefono': telefono, 'alloggio_nome': _s(data.get('alloggio_nome')),
            'spiaggia_nome': spiaggia, 'persone': persone, 'autista_nome': autista or None}, None


def _azione_staff_crea(db, origin, data):
    if not _staff_autenticato(data):
        return _json(origin, {'ok': False, 'errore': 'non_autorizzato'}, 401)
    cfg = _cfg_navetta(db)
    campi, err = _campi_corsa_staff(db, cfg, data)
    if err:
        return _json(origin, {'ok': False, 'errore': err}, 400)
    orario = _s(data.get('orario'), 5)
    if not _orario_staff_valido(orario, cfg):
        return _json(origin, {'ok': False, 'errore': 'orario_non_valido'}, 400)
    doc = {**campi, 'data': _oggi_iso(), 'orario': orario, 'stato': 'accettata', 'accettata_il': _now_iso(),
           'creato_il': _now_iso(), 'creato_da': _s(data.get('operatore'), 60), 'creata_da_staff': True}
    ref = db.collection('navetta_prenotazioni').document()
    err = _scrivi_se_libero(db.transaction(), db, cfg, ref, doc, None, orario, campi['nome'], campi['telefono'],
                            autista=campi['autista_nome'] or '', persone=campi['persone'], spiaggia=campi['spiaggia_nome'])
    if err:
        return _json(origin, {'ok': False, 'errore': err}, 409)
    return _json(origin, {'ok': True, 'id': ref.id})


def _carica_corsa_oggi(db, data):
    ref = db.collection('navetta_prenotazioni').document(_s(data.get('id'), 60) or '_')
    snap = ref.get()
    return ref, snap, (snap.to_dict() if snap.exists else None)


def _totale_della_corsa(db, c):
    """Persone della prenotazione a cui e' collegata la corsa (None se creata dallo staff)."""
    if not c.get('prenId'):
        return None
    try:
        pren = db.collection('prenotazioni').document(c['prenId']).get()
        return _persone_prenotazione(pren.to_dict() or {}) or None if pren.exists else None
    except Exception:
        return None


def _azione_staff_modifica(db, origin, data):
    if not _staff_autenticato(data):
        return _json(origin, {'ok': False, 'errore': 'non_autorizzato'}, 401)
    cfg = _cfg_navetta(db)
    ref, snap, c = _carica_corsa_oggi(db, data)
    if not c:
        return _json(origin, {'ok': False, 'errore': 'corsa_non_trovata'}, 404)
    campi, err = _campi_corsa_staff(db, cfg, data)
    if err:
        return _json(origin, {'ok': False, 'errore': err}, 400)
    orario = _s(data.get('orario'), 5) or c.get('orario') or ''
    cambia_ora = orario != c.get('orario')
    if cambia_ora and not _orario_staff_valido(orario, cfg):
        return _json(origin, {'ok': False, 'errore': 'orario_non_valido'}, 400)
    scrittura = {**campi, 'orario': orario, 'aggiornato_il': _now_iso(), 'modificato_da': _s(data.get('operatore'), 60)}
    if cambia_ora:
        scrittura['orario_precedente'] = c.get('orario') or ''
        scrittura['orario_modificato_il'] = _now_iso()
    if c.get('stato') not in ('in_attesa', 'accettata'):
        ref.update(scrittura)          # corsa chiusa: non occupa posti, nessun controllo
        return _json(origin, {'ok': True, 'id': snap.id})
    err = _scrivi_se_libero(db.transaction(), db, cfg, ref, scrittura, c.get('prenId'), orario, campi['nome'], campi['telefono'],
                            escludi_id=snap.id, autista=campi['autista_nome'] or '', persone=campi['persone'],
                            spiaggia=campi['spiaggia_nome'], totale=_totale_della_corsa(db, c))
    if err:
        return _json(origin, {'ok': False, 'errore': err}, 409)
    return _json(origin, {'ok': True, 'id': snap.id})


def _azione_staff_riapri(db, origin, data):
    """Riapre una corsa completata/annullata: solo se posti, spiaggia e
    persone della prenotazione lo permettono ancora."""
    if not _staff_autenticato(data):
        return _json(origin, {'ok': False, 'errore': 'non_autorizzato'}, 401)
    cfg = _cfg_navetta(db)
    ref, snap, c = _carica_corsa_oggi(db, data)
    if not c:
        return _json(origin, {'ok': False, 'errore': 'corsa_non_trovata'}, 404)
    if c.get('stato') in ('in_attesa', 'accettata'):
        return _json(origin, {'ok': True, 'id': snap.id})
    autista = _s(c.get('autista_nome'))
    err = _scrivi_se_libero(db.transaction(), db, cfg, ref,
                            {'stato': 'accettata' if autista else 'in_attesa', 'riaperta_il': _now_iso(), 'aggiornato_il': _now_iso()},
                            c.get('prenId'), c.get('orario') or '', c.get('nome'), c.get('telefono'),
                            escludi_id=snap.id, autista=autista, persone=_persone(c),
                            spiaggia=_s(c.get('spiaggia_nome')), totale=_totale_della_corsa(db, c))
    if err:
        return _json(origin, {'ok': False, 'errore': err}, 409)
    return _json(origin, {'ok': True, 'id': snap.id})


AZIONI = {
    'carica':                  _azione_carica,
    'contenuti':               _azione_contenuti,
    'navetta_stato':           _azione_navetta_stato,
    'navetta_prenota':         _azione_navetta_prenota,
    'navetta_modifica_orario': _azione_navetta_modifica_orario,
    'navetta_annulla':         _azione_navetta_annulla,
    'staff_crea':              _azione_staff_crea,
    'staff_modifica':          _azione_staff_modifica,
    'staff_riapri':            _azione_staff_riapri,
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
