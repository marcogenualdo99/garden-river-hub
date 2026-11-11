"""Pulizia automatica delle corse navetta concluse.

Cancella da `navetta_prenotazioni` le corse "completata" e "annullata" piu'
vecchie di N giorni (default 3, modificabile da Navetta > Impostazioni, doc
Firestore `impostazioni/navetta`, campo `pulizia_giorni`), cosi' la collezione
non si riempie di dati inutili.

Trigger HTTPS pensato per Cloud Scheduler (una volta al giorno, es. 04:00).
Serve il token condiviso (env PULIZIA_TOKEN), passato come ?token=... o
nell'header X-Pulizia-Token.
"""

import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import firebase_admin
from firebase_admin import firestore
import functions_framework

if not firebase_admin._apps:
    firebase_admin.initialize_app()

TZ_ROMA = ZoneInfo('Europe/Rome')
TOKEN = os.environ.get('PULIZIA_TOKEN', '').strip()
GIORNI_DEFAULT = 3


def _giorni(db):
    try:
        snap = db.collection('impostazioni').document('navetta').get()
        v = int((snap.to_dict() or {}).get('pulizia_giorni', GIORNI_DEFAULT)) if snap.exists else GIORNI_DEFAULT
        return v if v >= 1 else GIORNI_DEFAULT
    except Exception:
        return GIORNI_DEFAULT


@functions_framework.http
def navetta_pulizia(request):
    token = request.args.get('token') or request.headers.get('X-Pulizia-Token', '')
    if not TOKEN or token != TOKEN:
        return (json.dumps({'ok': False, 'errore': 'non autorizzato'}), 403,
                {'Content-Type': 'application/json'})

    db = firestore.client()
    giorni = _giorni(db)
    limite = (datetime.now(TZ_ROMA) - timedelta(days=giorni)).strftime('%Y-%m-%d')

    eliminate = 0
    batch = db.batch()
    in_batch = 0
    # Filtro per stato sul server, per data in Python: niente indice composto.
    for d in db.collection('navetta_prenotazioni').where('stato', 'in', ['completata', 'annullata']).stream():
        data = str((d.to_dict() or {}).get('data') or '')
        if data and data <= limite:
            batch.delete(d.reference)
            in_batch += 1
            eliminate += 1
            if in_batch >= 400:
                batch.commit()
                batch = db.batch()
                in_batch = 0
    if in_batch:
        batch.commit()

    print(f'Pulizia navetta: {eliminate} corse eliminate (data <= {limite}, {giorni} giorni)')
    return (json.dumps({'ok': True, 'eliminate': eliminate, 'giorni': giorni}), 200,
            {'Content-Type': 'application/json'})
