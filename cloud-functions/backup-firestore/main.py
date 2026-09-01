"""Backup automatico del Firestore di Garden Hub.

Fa partire un export gestito di TUTTE le collezioni (sottocollezioni comprese,
es. prenotazioni/<id>/log) verso un bucket Google Cloud Storage di proprieta'
della struttura. E' l'export ufficiale di Firestore: si ripristina con
`gcloud firestore import gs://.../<cartella>` (v. README).

Trigger HTTPS, pensato per essere chiamato ogni notte da Cloud Scheduler; si
puo' anche lanciare a mano aprendo l'URL con ?token=... . In entrambi i casi
serve il token condiviso (env BACKUP_TOKEN): un export costa e non deve poter
partire da chiunque trovi l'URL.

Variabili d'ambiente di runtime:
  BACKUP_TOKEN   (obbligatoria) segreto condiviso con Cloud Scheduler
  BACKUP_BUCKET  (obbligatoria) es. gs://garden-river-backup
  GCP_PROJECT_ID (opzionale)    default: garden-river-conti-febed
  FIRESTORE_DATABASE (opzionale) default: (default)
"""

import json
import os
from datetime import datetime, timezone

from google.cloud import firestore_admin_v1
import functions_framework

PROJECT_ID   = os.environ.get('GCP_PROJECT_ID', 'garden-river-conti-febed')
DATABASE_ID  = os.environ.get('FIRESTORE_DATABASE', '(default)')
BUCKET       = os.environ.get('BACKUP_BUCKET', '').strip()
BACKUP_TOKEN = os.environ.get('BACKUP_TOKEN', '').strip()


def _avvia_export():
    if not BUCKET:
        raise RuntimeError('BACKUP_BUCKET non configurato')
    client = firestore_admin_v1.FirestoreAdminClient()
    database = client.database_path(PROJECT_ID, DATABASE_ID)
    # Una cartella per esecuzione, con data e ora UTC: cosi' i backup non si
    # sovrascrivono mai e si ordinano da soli.
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M%S')
    prefix = BUCKET.rstrip('/') + '/' + stamp
    operazione = client.export_documents(request={
        'name': database,
        'output_uri_prefix': prefix,
    })
    return prefix, operazione.operation.name


@functions_framework.http
def backup_firestore(request):
    if request.method == 'OPTIONS':
        return ('', 204, {'Access-Control-Allow-Origin': '*',
                          'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
                          'Access-Control-Allow-Headers': 'Content-Type, X-Backup-Token'})

    token = request.args.get('token') or request.headers.get('X-Backup-Token', '')
    if not BACKUP_TOKEN or token != BACKUP_TOKEN:
        return (json.dumps({'ok': False, 'errore': 'non autorizzato'}), 403,
                {'Content-Type': 'application/json'})

    try:
        prefix, op_name = _avvia_export()
        print(f'Export Firestore avviato -> {prefix} ({op_name})')
        # L'export gira in background lato Google: rispondiamo appena e' stato
        # accettato, non aspettiamo che finisca.
        return (json.dumps({'ok': True, 'destinazione': prefix, 'operazione': op_name}),
                200, {'Content-Type': 'application/json'})
    except Exception as e:
        print(f'Errore avvio export Firestore: {e}')
        return (json.dumps({'ok': False, 'errore': str(e)}), 500,
                {'Content-Type': 'application/json'})
