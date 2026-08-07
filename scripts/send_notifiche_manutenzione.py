import os, json, requests
from google.oauth2 import service_account
import google.auth.transport.requests

PROJECT_ID = 'garden-river-conti-febed'
SCOPES     = ['https://www.googleapis.com/auth/cloud-platform']
BASE_FS    = f'https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents'
FCM_URL    = f'https://fcm.googleapis.com/v1/projects/{PROJECT_ID}/messages:send'
SITE_URL   = 'https://www.gardenhub.it'

# ── Auth ─────────────────────────────────────────────────────────────────────
sa_info = json.loads(os.environ['FCM_SERVICE_ACCOUNT_JSON'])
creds   = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
creds.refresh(google.auth.transport.requests.Request())
headers = {'Authorization': f'Bearer {creds.token}', 'Content-Type': 'application/json'}

# ── Query: ticket non ancora notificati ──────────────────────────────────────
r = requests.post(f'{BASE_FS}:runQuery', headers=headers, json={
    'structuredQuery': {
        'from': [{'collectionId': 'maintenance_tickets'}],
        'where': {
            'fieldFilter': {
                'field': {'fieldPath': 'notified'},
                'op': 'EQUAL',
                'value': {'booleanValue': False}
            }
        }
    }
})
docs = [d for d in r.json() if 'document' in d]

if not docs:
    print('Nessun ticket da notificare. Uscita.')
    exit(0)

print(f'Trovati {len(docs)} ticket da notificare')

# ── Leggi staffTokens con notifiche attive ───────────────────────────────────
r2         = requests.get(f'{BASE_FS}/staffTokens', headers=headers)
staff_docs = r2.json().get('documents', [])

fcm_tokens = []
for doc in staff_docs:
    fields = doc.get('fields', {})
    if fields.get('notifiche', {}).get('booleanValue', False):
        values = fields.get('tokens', {}).get('arrayValue', {}).get('values', [])
        fcm_tokens.extend(t['stringValue'] for t in values if 'stringValue' in t)

if not fcm_tokens:
    print('Nessun operatore con notifiche attive.')
else:
    print(f'Invio a {len(fcm_tokens)} dispositivo/i')

# ── Invia una notifica per ogni ticket non notificato ────────────────────────
for entry in docs:
    doc      = entry['document']
    doc_id   = doc['name'].split('/')[-1]
    fields   = doc.get('fields', {})

    unit     = fields.get('housing_unit', {}).get('stringValue', 'Alloggio sconosciuto')
    category = fields.get('category',     {}).get('stringValue', 'Altro')
    desc     = fields.get('issue_description', {}).get('stringValue', '')
    op       = fields.get('user_id',      {}).get('stringValue', '')

    title = f'🔧 Nuovo ticket: {category}'
    body  = f'{unit}' + (f' — {desc[:80]}' if desc else '')
    if op:
        body += f' (da {op})'

    print(f'  Ticket {doc_id}: "{title}" — "{body}"')

    for tok in fcm_tokens:
        payload = {
            'message': {
                'token': tok,
                'webpush': {
                    'notification': {
                        'title': title,
                        'body':  body,
                        'icon':  f'{SITE_URL}/logo-hub-app.jpg',
                        'badge': f'{SITE_URL}/logo-hub-app.jpg',
                        'tag':   f'ticket-{doc_id}',
                        'requireInteraction': True
                    },
                    'fcm_options': {'link': f'{SITE_URL}/manutenzione/'}
                }
            }
        }
        res = requests.post(FCM_URL, headers=headers, json=payload)
        if res.status_code == 200:
            print(f'    OK → {tok[:24]}...')
        else:
            print(f'    ERRORE {res.status_code} → {res.text[:300]}')

    # ── Marca il ticket come notificato ──────────────────────────────────────
    patch_url = f'{BASE_FS}/maintenance_tickets/{doc_id}?updateMask.fieldPaths=notified'
    requests.patch(patch_url, headers=headers, json={
        'fields': {'notified': {'booleanValue': True}}
    })
    print(f'  Ticket {doc_id} marcato come notificato')
