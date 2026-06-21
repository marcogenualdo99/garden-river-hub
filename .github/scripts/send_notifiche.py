import os, json, datetime, requests
from google.oauth2 import service_account
import google.auth.transport.requests

PROJECT_ID = 'garden-river-conti-febed'
SCOPES     = ['https://www.googleapis.com/auth/cloud-platform']
BASE_FS    = f'https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents'
FCM_URL    = f'https://fcm.googleapis.com/v1/projects/{PROJECT_ID}/messages:send'
SITE_URL   = 'https://www.gardenhub.it'

# ── Auth ────────────────────────────────────────────────────────────────────
sa_info = json.loads(os.environ['FCM_SERVICE_ACCOUNT_JSON'])
creds   = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
creds.refresh(google.auth.transport.requests.Request())
headers = {'Authorization': f'Bearer {creds.token}', 'Content-Type': 'application/json'}

# ── Data di domani ───────────────────────────────────────────────────────────
tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
print(f'Controllo conti aperti con checkout: {tomorrow}')

# ── Query Firestore: ospiti non chiusi con checkout domani ───────────────────
r = requests.post(f'{BASE_FS}:runQuery', headers=headers, json={
    'structuredQuery': {
        'from': [{'collectionId': 'ospiti'}],
        'where': {
            'compositeFilter': {
                'op': 'AND',
                'filters': [
                    {'fieldFilter': {'field': {'fieldPath': 'chiuso'}, 'op': 'EQUAL',
                                     'value': {'booleanValue': False}}},
                    {'fieldFilter': {'field': {'fieldPath': 'checkout'}, 'op': 'EQUAL',
                                     'value': {'stringValue': tomorrow}}}
                ]
            }
        }
    }
})
conti = [doc['document']['fields'] for doc in r.json() if 'document' in doc]

if not conti:
    print('Nessun conto aperto con checkout domani. Uscita.')
    exit(0)

n     = len(conti)
nomi  = [f"{c['cognome']['stringValue']} {c['nome']['stringValue']}" for c in conti]
title = f"{'1 checkout' if n == 1 else f'{n} checkout'} domani"
body  = nomi[0] if n == 1 else f"{nomi[0]} e altri {n - 1}"
print(f'Notifica: "{title}" — "{body}"')

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
    print('Nessun operatore con notifiche attive. Uscita.')
    exit(0)

print(f'Invio a {len(fcm_tokens)} dispositivo/i')

# ── Invia notifiche FCM ──────────────────────────────────────────────────────
for tok in fcm_tokens:
    payload = {
        'message': {
            'token': tok,
            'notification': {'title': title, 'body': body},
            'webpush': {
                'notification': {
                    'title': title,
                    'body':  body,
                    'icon':  f'{SITE_URL}/logo-hub-app.jpg',
                    'badge': f'{SITE_URL}/logo-hub-app.jpg',
                    'tag':   'checkout-reminder',
                    'requireInteraction': True
                },
                'fcm_options': {'link': f'{SITE_URL}/conti/'}
            }
        }
    }
    res = requests.post(FCM_URL, headers=headers, json=payload)
    if res.status_code == 200:
        print(f'  OK → {tok[:24]}...')
    else:
        print(f'  ERRORE {res.status_code} → {res.text[:300]}')
