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


def query_non_notificati(collection_id):
    r = requests.post(f'{BASE_FS}:runQuery', headers=headers, json={
        'structuredQuery': {
            'from': [{'collectionId': collection_id}],
            'where': {
                'fieldFilter': {
                    'field': {'fieldPath': 'notified'},
                    'op': 'EQUAL',
                    'value': {'booleanValue': False}
                }
            }
        }
    })
    return [d for d in r.json() if 'document' in d]


def invia_push(tokens, title, body, tag):
    for tok in tokens:
        payload = {
            'message': {
                'token': tok,
                'webpush': {
                    'notification': {
                        'title': title,
                        'body':  body,
                        'icon':  f'{SITE_URL}/logo-hub-app.jpg',
                        'badge': f'{SITE_URL}/logo-hub-app.jpg',
                        'tag':   tag,
                        'requireInteraction': True
                    },
                    'fcm_options': {'link': f'{SITE_URL}/ristorazione/staff.html'}
                }
            }
        }
        res = requests.post(FCM_URL, headers=headers, json=payload)
        if res.status_code == 200:
            print(f'    OK → {tok[:24]}...')
        else:
            print(f'    ERRORE {res.status_code} → {res.text[:300]}')


ordini_docs = query_non_notificati('ordini_ristorazione')
test_docs   = query_non_notificati('test_notifiche')

if not ordini_docs and not test_docs:
    print('Nessun ordine e nessuna richiesta di test da notificare. Uscita.')
    exit(0)

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

# ── Invia una notifica per ogni ordine non notificato ─────────────────────────
if ordini_docs:
    print(f'Trovati {len(ordini_docs)} ordine/i da notificare')

for entry in ordini_docs:
    doc      = entry['document']
    doc_id   = doc['name'].split('/')[-1]
    fields   = doc.get('fields', {})

    famiglia = fields.get('famiglia_nome', {}).get('stringValue', 'Ospite sconosciuto')
    unita    = fields.get('unita',         {}).get('stringValue', '')
    tipo     = fields.get('tipo',          {}).get('stringValue', '')
    note     = fields.get('note',          {}).get('stringValue', '')

    piatti_values = fields.get('piatti', {}).get('arrayValue', {}).get('values', [])
    piatti = []
    for v in piatti_values:
        pf = v.get('mapValue', {}).get('fields', {})
        nome = pf.get('piatto', {}).get('stringValue', '—')
        qta  = pf.get('quantita', {}).get('integerValue') or pf.get('quantita', {}).get('doubleValue') or 1
        piatti.append(f'{qta}x {nome}')

    pasto = {'pranzo': 'Pranzo', 'cena': 'Cena'}.get(tipo, tipo or 'Pasto')
    title = f'🍽️ Nuovo ordine: {famiglia}'
    body_parts = [p for p in [unita, ', '.join(piatti[:4])] if p]
    if len(piatti) > 4:
        body_parts[-1] += f' e altri {len(piatti) - 4}'
    body = f'{pasto} — ' + (' · '.join(body_parts) if body_parts else 'nessun piatto')
    if note:
        body += f' (nota: {note[:60]})'

    print(f'  Ordine {doc_id}: "{title}" — "{body}"')
    invia_push(fcm_tokens, title, body, f'ordine-{doc_id}')

    # ── Marca l'ordine come notificato ────────────────────────────────────────
    patch_url = f'{BASE_FS}/ordini_ristorazione/{doc_id}?updateMask.fieldPaths=notified'
    requests.patch(patch_url, headers=headers, json={
        'fields': {'notified': {'booleanValue': True}}
    })
    print(f'  Ordine {doc_id} marcato come notificato')

# ── Invia notifiche di test richieste dal pulsante in staff.html ─────────────
if test_docs:
    print(f'Trovate {len(test_docs)} richieste di notifica test')

for entry in test_docs:
    doc      = entry['document']
    doc_id   = doc['name'].split('/')[-1]
    fields   = doc.get('fields', {})
    chi      = fields.get('richiesto_da', {}).get('stringValue', 'Staff')

    title = '🔔 Notifica di test'
    body  = f'Le notifiche push funzionano correttamente (richiesta da {chi})'

    print(f'  Test {doc_id}: "{title}" — "{body}"')
    invia_push(fcm_tokens, title, body, f'test-{doc_id}')

    # ── Elimina la richiesta di test (non serve conservarla) ───────────────────
    requests.delete(f'{BASE_FS}/test_notifiche/{doc_id}', headers=headers)
    print(f'  Richiesta di test {doc_id} eliminata')
