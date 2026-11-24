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
  - rinnova  : { id_token }                 -> nuovo token di sessione (per le app Firebase
                                               secondarie), solo se l'id_token è già di un operatore
  - migra    : { token[, pulisci] }         -> una tantum, dai PIN in chiaro agli hash

SESSIONE: verifica/imposta/rinnova rispondono anche con `token`, un custom token
Firebase (claim `operatore`, `ruolo`, `nome`). Il browser lo scambia con
signInWithCustomToken: da quel momento le regole Firestore/Storage riconoscono
l'operatore (`request.auth.token.operatore == true`). Gli accessi anonimi non
hanno più accesso ai dati. Serve il ruolo IAM "Service Account Token Creator"
sul service account della funzione (vedi README).
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

import firebase_admin
from firebase_admin import firestore, auth as fb_auth
import functions_framework

if not firebase_admin._apps:
    firebase_admin.initialize_app()

ALLOWED_ORIGINS = {'https://gardenhub.it', 'https://www.gardenhub.it'}

PBKDF2_ITER   = 200_000
SALT_BYTES    = 16
MAX_TENTATIVI = 5                      # errori consecutivi prima di un blocco
# Blocco PROGRESSIVO: ogni serie di errori allunga l'attesa (1°, 2°, 3°, 4° e successivi).
# Si azzera con un accesso riuscito, o dopo DECADIMENTO_ORE senza errori.
BLOCCHI_MINUTI = [15, 60, 240, 1440]
DECADIMENTO_ORE = 24
PIN_MIN_LEN   = 6                      # il client chiede gia' 6 cifre: ora lo impone anche il server
PIN_MAX_LEN   = 12

# CODICE DI ATTIVAZIONE: senza, chiunque conosca il nome potrebbe scegliere il primo PIN di un
# operatore che non ne ha uno (nuovo operatore, o appena resettato). Lo genera un admin e lo
# consegna al collega: 6 cifre, monouso, scade dopo ATTIVAZIONE_ORE, nel DB solo l'hash.
ATTIVAZIONE_ORE = 24
ATTIVAZIONE_MAX_TENTATIVI = 5          # errori sul codice: poi va rigenerato
CODICE_LEN = 6

# Limite per IP: dopo troppi PIN sbagliati dallo stesso indirizzo si risponde 429 SENZA toccare
# i contatori degli operatori (altrimenti chiunque potrebbe bloccare un collega a distanza).
IP_MAX_FALLITI = 15
IP_FINESTRA_S  = 600
_IP_FALLITI = {}                       # ip -> [timestamp] (in memoria, per istanza)


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


def _nuovo_codice_attivazione(db, nome, creato_da):
    """Crea (o sostituisce) il codice di attivazione di `nome`. Ritorna (codice_in_chiaro, scadenza_ms)."""
    codice = '%0*d' % (CODICE_LEN, secrets.randbelow(10 ** CODICE_LEN))
    salt_b64 = base64.b64encode(secrets.token_bytes(SALT_BYTES)).decode('ascii')
    scade = _now_ms() + ATTIVAZIONE_ORE * 3600 * 1000
    db.collection('operatori_attivazione').document(nome).set({
        'hash': _hash_pin(codice, salt_b64), 'salt': salt_b64, 'iter': PBKDF2_ITER,
        'scade': scade, 'tentativi': 0, 'creato_da': creato_da, 'creato_il': _now_ms(),
    })
    return codice, scade


def _bootstrap_aperto(db, nome):
    """True solo se `nome` e' un admin e NESSUN admin ha ancora un PIN (prima installazione, o
    recupero se tutti i PIN admin sono stati azzerati): serve a non restare senza nessuno che possa
    generare i codici. Con almeno un admin che ha un PIN non si apre mai."""
    if _ruolo(db, nome) != 'admin':
        return False
    for doc in db.collection('operatori').where('ruolo', '==', 'admin').stream():
        if db.collection('operatori_pin').document(doc.id).get().exists:
            return False
    return True


def _admin_da_token(db, data):
    """(nome_admin, None) se id_token e' di un admin in carica (ruolo riletto dal DB), altrimenti (None, errore)."""
    try:
        dec = fb_auth.verify_id_token(str(data.get('id_token') or '')[:4000])
    except Exception:
        return None, ({'ok': False, 'errore': 'sessione_non_valida'}, 401)
    admin_nome = dec.get('nome')
    if not dec.get('operatore') or not _nome_valido(admin_nome) or _ruolo(db, admin_nome) != 'admin':
        return None, ({'ok': False, 'errore': 'non_autorizzato'}, 403)
    return admin_nome, None


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


def _token_sessione(db, nome):
    """Custom token Firebase per l'operatore `nome`, con ruolo letto dal DB."""
    ruolo = _ruolo(db, nome)
    tok = fb_auth.create_custom_token(
        'op:' + nome,
        {'operatore': True, 'ruolo': ruolo, 'nome': nome},
    )
    return tok.decode('ascii') if isinstance(tok, bytes) else tok


def _ruolo(db, nome):
    snap = db.collection('operatori').document(nome).get()
    if not snap.exists:
        return 'operatore'
    return (snap.to_dict() or {}).get('ruolo', 'operatore')


def _ip_bloccato(ip):
    """Minuti di attesa residui se l'IP ha troppi errori recenti, altrimenti 0."""
    adesso = time.time()
    lista = [t for t in _IP_FALLITI.get(ip, []) if adesso - t < IP_FINESTRA_S]
    if lista:
        _IP_FALLITI[ip] = lista
    else:
        _IP_FALLITI.pop(ip, None)
    if len(_IP_FALLITI) > 5000:        # memoria limitata
        _IP_FALLITI.clear()
    if len(lista) >= IP_MAX_FALLITI:
        return max(1, int((IP_FINESTRA_S - (adesso - lista[0])) // 60) + 1)
    return 0


def _ip_fallito(ip):
    _IP_FALLITI.setdefault(ip, []).append(time.time())


def _verifica_pin(db, nome, pin):
    """Ritorna (esito, dettaglio) con esito in {'ok','errato','nessun_pin','bloccato'}.
    Conteggio tentativi in TRANSAZIONE: richieste parallele non possono aggirare il limite."""
    ref = db.collection('operatori_pin').document(nome)

    @firestore.transactional
    def _tx(tx):
        snap = ref.get(transaction=tx)
        if not snap.exists:
            return 'nessun_pin', None
        d = snap.to_dict() or {}
        adesso = _now_ms()

        bloccato_fino = d.get('bloccato_fino') or 0
        if bloccato_fino > adesso:
            return 'bloccato', max(1, round((bloccato_fino - adesso) / 60000))

        atteso    = d.get('hash') or ''
        calcolato = _hash_pin(pin, d.get('salt') or '', d.get('iter') or PBKDF2_ITER)
        if atteso and hmac.compare_digest(atteso, calcolato):
            if d.get('tentativi') or d.get('bloccato_fino') or d.get('blocchi'):
                tx.update(ref, {'tentativi': 0, 'bloccato_fino': 0, 'blocchi': 0})
            return 'ok', None

        blocchi   = d.get('blocchi') or 0
        tentativi = d.get('tentativi') or 0
        # Il decadimento parte dalla FINE dell'ultimo blocco (non dall'ultimo errore): altrimenti
        # un blocco da 24 ore scadrebbe "vecchio" e si ripartirebbe subito dal gradino da 15 minuti.
        ultimo    = max(d.get('ultimo_errore') or 0, d.get('bloccato_fino') or 0)
        if ultimo and adesso - ultimo > DECADIMENTO_ORE * 3600 * 1000:
            blocchi, tentativi = 0, 0          # errori vecchi: si riparte da zero
        tentativi += 1
        if tentativi >= MAX_TENTATIVI:
            minuti = BLOCCHI_MINUTI[min(blocchi, len(BLOCCHI_MINUTI) - 1)]
            tx.update(ref, {'tentativi': 0, 'blocchi': blocchi + 1, 'ultimo_errore': adesso,
                            'bloccato_fino': adesso + minuti * 60000})
            return 'bloccato', minuti
        tx.update(ref, {'tentativi': tentativi, 'blocchi': blocchi, 'ultimo_errore': adesso})
        return 'errato', None

    return _tx(db.transaction())


# ── azioni ─────────────────────────────────────────────────────────────────

def _azione_verifica(db, origin, data):
    nome = (data.get('nome') or '').strip()
    pin  = data.get('pin') or ''
    if not nome or not pin:
        return _json(origin, {'ok': False, 'errore': 'dati_mancanti'}, 400)
    if not _nome_valido(nome):
        return _json(origin, {'ok': False, 'errore': 'nessun_pin'})
    if not isinstance(pin, str) or len(pin) > 64:
        return _json(origin, {'ok': False, 'errore': 'pin_errato'})
    ip = data.get('_ip') or '?'
    attesa = _ip_bloccato(ip)
    if attesa:                                   # non conta contro l'operatore
        return _json(origin, {'ok': False, 'errore': 'troppi_tentativi', 'minuti': attesa}, 429)
    esito, dettaglio = _verifica_pin(db, nome, pin)
    if esito == 'errato':
        _ip_fallito(ip)
    if esito == 'ok':
        return _json(origin, {'ok': True, 'ruolo': _ruolo(db, nome),
                              'token': _token_sessione(db, nome)})
    if esito == 'bloccato':
        return _json(origin, {'ok': False, 'errore': 'bloccato', 'minuti': dettaglio})
    if esito == 'nessun_pin':
        return _json(origin, {'ok': False, 'errore': 'nessun_pin'})
    return _json(origin, {'ok': False, 'errore': 'pin_errato'})


def _azione_imposta(db, origin, data):
    """Primo PIN di un operatore. Richiede il CODICE DI ATTIVAZIONE dato da un admin (salvo la
    prima installazione, vedi _bootstrap_aperto). Codice e PIN si consumano/scrivono in transazione."""
    nome = (data.get('nome') or '').strip()
    pin  = data.get('pin') or ''
    if not nome or not _nome_valido(nome):
        return _json(origin, {'ok': False, 'errore': 'dati_mancanti'}, 400)
    if not _pin_valido(pin):
        return _json(origin, {'ok': False, 'errore': 'pin_non_valido'}, 400)
    ip = data.get('_ip') or '?'
    attesa = _ip_bloccato(ip)
    if attesa:
        return _json(origin, {'ok': False, 'errore': 'troppi_tentativi', 'minuti': attesa}, 429)
    op_ref  = db.collection('operatori').document(nome)
    pin_ref = db.collection('operatori_pin').document(nome)
    att_ref = db.collection('operatori_attivazione').document(nome)
    if not op_ref.get().exists:
        return _json(origin, {'ok': False, 'errore': 'operatore_sconosciuto'}, 404)
    codice = data.get('codice')
    codice = codice.strip() if isinstance(codice, str) and len(codice) <= 32 else ''
    bootstrap = (not att_ref.get().exists) and _bootstrap_aperto(db, nome)

    @firestore.transactional
    def _tx(tx):
        if pin_ref.get(transaction=tx).exists:
            return 'pin_gia_impostato'
        a = att_ref.get(transaction=tx)
        if bootstrap and not a.exists:
            pass
        else:
            if not a.exists:
                return 'codice_richiesto'
            d = a.to_dict() or {}
            if (d.get('scade') or 0) < _now_ms():
                tx.delete(att_ref)
                return 'codice_scaduto'
            calcolato = _hash_pin(codice, d.get('salt') or '', d.get('iter') or PBKDF2_ITER)
            if not (codice and hmac.compare_digest(d.get('hash') or '', calcolato)):
                t = (d.get('tentativi') or 0) + 1
                if t >= ATTIVAZIONE_MAX_TENTATIVI:
                    tx.delete(att_ref)          # troppi errori: l'admin ne genera un altro
                    return 'codice_scaduto'
                tx.update(att_ref, {'tentativi': t})
                return 'codice_errato'
            tx.delete(att_ref)                  # monouso
        tx.set(pin_ref, _nuovo_record(pin))
        tx.update(op_ref, {'haPin': True})
        return 'ok'

    esito = _tx(db.transaction())
    if esito == 'ok':
        return _json(origin, {'ok': True, 'ruolo': _ruolo(db, nome), 'token': _token_sessione(db, nome)})
    if esito == 'pin_gia_impostato':
        return _json(origin, {'ok': False, 'errore': esito}, 409)
    if esito in ('codice_errato', 'codice_scaduto'):
        _ip_fallito(ip)
    return _json(origin, {'ok': False, 'errore': esito}, 403)


def _azione_stato_attivazione(db, origin, data):
    """Il login chiede se per questo operatore serve il codice di attivazione (false solo nella
    prima installazione, quando nessun admin ha ancora un PIN)."""
    nome = (data.get('nome') or '').strip()
    if not _nome_valido(nome):
        return _json(origin, {'ok': True, 'richiesto': True})
    richiesto = True
    if db.collection('operatori').document(nome).get().exists \
            and not db.collection('operatori_attivazione').document(nome).get().exists:
        richiesto = not _bootstrap_aperto(db, nome)
    return _json(origin, {'ok': True, 'richiesto': richiesto})


def _azione_codice_attivazione(db, origin, data):
    """Un admin genera il codice di attivazione per un operatore SENZA PIN (nuovo operatore)."""
    admin_nome, err = _admin_da_token(db, data)
    if err:
        return _json(origin, err[0], err[1])
    nome = (data.get('nome') or '').strip()
    if not _nome_valido(nome):
        return _json(origin, {'ok': False, 'errore': 'dati_mancanti'}, 400)
    if not db.collection('operatori').document(nome).get().exists:
        return _json(origin, {'ok': False, 'errore': 'operatore_sconosciuto'}, 404)
    if db.collection('operatori_pin').document(nome).get().exists:
        return _json(origin, {'ok': False, 'errore': 'pin_gia_impostato'}, 409)   # per chi ha un PIN: Reset PIN
    codice, scade = _nuovo_codice_attivazione(db, nome, admin_nome)
    print(f'attivazione: {admin_nome} ha creato un codice per {nome}')
    return _json(origin, {'ok': True, 'codice': codice, 'scade': scade})


def _azione_rinnova(db, origin, data):
    """Nuovo custom token a chi ha già una sessione operatore valida. Serve alle
    app Firebase con nome (ognuna ha la propria sessione). Rilegge l'operatore
    dal DB: se è stato rimosso, non rinnova."""
    try:
        dec = fb_auth.verify_id_token(str(data.get('id_token') or '')[:4000])
    except Exception:
        return _json(origin, {'ok': False, 'errore': 'sessione_non_valida'}, 401)
    nome = dec.get('nome')
    if not dec.get('operatore') or not _nome_valido(nome):
        return _json(origin, {'ok': False, 'errore': 'sessione_non_valida'}, 401)
    if not db.collection('operatori').document(nome).get().exists:
        return _json(origin, {'ok': False, 'errore': 'operatore_rimosso'}, 403)
    return _json(origin, {'ok': True, 'ruolo': _ruolo(db, nome),
                          'token': _token_sessione(db, nome)})


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
    if not isinstance(admin_pin, str) or len(admin_pin) > 64:
        return _json(origin, {'ok': False, 'errore': 'pin_admin_errato'}, 403)
    ip = data.get('_ip') or '?'
    attesa = _ip_bloccato(ip)
    if attesa:
        return _json(origin, {'ok': False, 'errore': 'troppi_tentativi', 'minuti': attesa}, 429)
    esito, dettaglio = _verifica_pin(db, admin_nome, admin_pin)
    if esito == 'errato':
        _ip_fallito(ip)
    if esito != 'ok':
        if esito == 'bloccato':
            return _json(origin, {'ok': False, 'errore': 'bloccato', 'minuti': dettaglio})
        return _json(origin, {'ok': False, 'errore': 'pin_admin_errato'}, 403)
    db.collection('operatori_pin').document(nome).delete()
    try:
        db.collection('operatori').document(nome).update({'haPin': False})
    except Exception as e:  # documento operatore inesistente: non è un problema
        print(f'reset: haPin non aggiornato per {nome}: {e}')
    # Il collega sceglierà il nuovo PIN solo con questo codice (altrimenti chiunque potrebbe farlo prima di lui)
    codice, scade = _nuovo_codice_attivazione(db, nome, admin_nome)
    return _json(origin, {'ok': True, 'codice': codice, 'scade': scade})


def _azione_sblocca(db, origin, data):
    """Un amministratore con sessione valida toglie il blocco a un operatore SENZA cambiargli il PIN
    (azzera tentativi e blocchi progressivi). Vale anche per se stesso: se un attaccante lo ha
    bloccato, la sua sessione ancora aperta basta per rientrare. Ruolo riletto dal DB, non dal token."""
    admin_nome, err = _admin_da_token(db, data)
    if err:
        return _json(origin, err[0], err[1])
    nome = (data.get('nome') or '').strip()
    if not _nome_valido(nome):
        return _json(origin, {'ok': False, 'errore': 'dati_mancanti'}, 400)
    ref = db.collection('operatori_pin').document(nome)
    if not ref.get().exists:
        return _json(origin, {'ok': False, 'errore': 'nessun_pin'}, 404)
    ref.update({'tentativi': 0, 'bloccato_fino': 0, 'blocchi': 0, 'ultimo_errore': 0})
    print(f'sblocca: {admin_nome} ha sbloccato {nome}')
    return _json(origin, {'ok': True})


# Collezioni con un documento per operatore (id = nome): vanno tutte svuotate quando si rimuove qualcuno.
COLLEZIONI_PER_OPERATORE = ('operatori', 'operatori_pin', 'operatori_attivazione', 'permessi', 'home_layout')


def _elimina_dati_operatore(db, nome):
    """Cancella tutto cio' che porta il nome dell'operatore e ne chiude le sessioni.
    Ritorna l'elenco di cio' che c'era. L'utente Firebase Auth ('op:<nome>') si elimina: senza,
    il suo refresh token continuerebbe a dare accesso ai dati (le regole guardano solo il claim)."""
    fatti = []
    for col in COLLEZIONI_PER_OPERATORE:           # 'operatori' per primo: 'rinnova' smette subito di funzionare
        ref = db.collection(col).document(nome)
        if ref.get().exists:
            ref.delete()
            fatti.append(col)
    try:
        fb_auth.delete_user('op:' + nome)
        fatti.append('auth')
    except Exception:                               # utente mai creato / gia' eliminato
        pass
    return fatti


def _azione_rimuovi(db, origin, data):
    """Un admin rimuove un operatore: documento, PIN, codice di attivazione, permessi, layout home e
    utente Auth (con le sue sessioni). Non ci si rimuove da soli: chi chiama e' sempre un altro admin,
    quindi almeno un admin resta."""
    admin_nome, err = _admin_da_token(db, data)
    if err:
        return _json(origin, err[0], err[1])
    nome = (data.get('nome') or '').strip()
    if not _nome_valido(nome):
        return _json(origin, {'ok': False, 'errore': 'dati_mancanti'}, 400)
    if nome == admin_nome:
        return _json(origin, {'ok': False, 'errore': 'non_puoi_rimuovere_te_stesso'}, 409)
    fatti = _elimina_dati_operatore(db, nome)
    print(f'rimuovi: {admin_nome} ha rimosso {nome} ({", ".join(fatti) or "niente"})')
    return _json(origin, {'ok': True, 'eliminati': fatti})


def _azione_pulisci_orfani(db, origin, data):
    """Toglie i dati di operatori GIA' cancellati in passato (PIN, codici, permessi, layout home, utenti
    Auth 'op:*'). Con dry_run (default) elenca soltanto. Si rifiuta se l'elenco operatori e' vuoto o
    senza admin, per non cancellare tutto per errore."""
    admin_nome, err = _admin_da_token(db, data)
    if err:
        return _json(origin, err[0], err[1])
    dry = data.get('dry_run') is not False
    attuali = {d.id: (d.to_dict() or {}) for d in db.collection('operatori').stream()}
    if not attuali or not any((v.get('ruolo') == 'admin') for v in attuali.values()):
        return _json(origin, {'ok': False, 'errore': 'elenco_operatori_non_affidabile'}, 409)
    orfani = {}
    for col in COLLEZIONI_PER_OPERATORE[1:]:
        ids = [d.id for d in db.collection(col).stream() if d.id not in attuali]
        if ids:
            orfani[col] = ids
    utenti = []
    try:
        for u in fb_auth.list_users().iterate_all():
            if (u.uid or '').startswith('op:') and u.uid[3:] not in attuali:
                utenti.append(u.uid[3:])
    except Exception as e:
        print(f'pulisci_orfani: elenco utenti Auth non disponibile: {e}')
    if utenti:
        orfani['auth'] = utenti
    if not dry:
        for col, ids in orfani.items():
            if col == 'auth':
                for nome in ids:
                    try:
                        fb_auth.delete_user('op:' + nome)
                    except Exception as e:
                        print(f'pulisci_orfani: utente {nome} non eliminato: {e}')
            else:
                for i in ids:
                    db.collection(col).document(i).delete()
        print(f'pulisci_orfani: {admin_nome} ha eliminato {sum(len(v) for v in orfani.values())} elementi')
    return _json(origin, {'ok': True, 'dry_run': dry, 'orfani': orfani,
                          'totale': sum(len(v) for v in orfani.values())})


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
    'rinnova':  _azione_rinnova,
    'sblocca':  _azione_sblocca,
    'rimuovi':  _azione_rimuovi,
    'pulisci_orfani': _azione_pulisci_orfani,
    'stato_attivazione':   _azione_stato_attivazione,
    'codice_attivazione':  _azione_codice_attivazione,
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
    if not isinstance(data, dict):
        return _json(origin, {'ok': False, 'errore': 'azione_non_valida'}, 400)
    handler = AZIONI.get(data.get('azione'))
    if not handler:
        return _json(origin, {'ok': False, 'errore': 'azione_non_valida'}, 400)
    # IP del chiamante (ULTIMO elemento di X-Forwarded-For, aggiunto da Google): serve solo al
    # limite per IP. Sovrascrive sempre un eventuale '_ip' mandato dal client.
    data['_ip'] = (request.headers.get('X-Forwarded-For', '').split(',')[-1].strip()
                   or request.remote_addr or '')

    try:
        return handler(firestore.client(), origin, data)
    except Exception as e:
        print(f'Errore azione {data.get("azione")}: {e}')
        return _json(origin, {'ok': False, 'errore': 'errore_interno'}, 500)
