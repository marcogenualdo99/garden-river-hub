import os, json
import requests
from google.oauth2 import service_account
import google.auth.transport.requests

# Controllo di sicurezza quotidiano sui token push in staffTokens: usa
# validate_only per chiedere a FCM se un token è ancora registrato, SENZA
# inviare nulla allo staff. Un token può morire mentre il dispositivo resta
# spento/inattivo per giorni: senza questo controllo lo scopriamo solo
# quando un ordine vero fallisce silenziosamente. Qui lo scopriamo prima,
# lo ripuliamo, e chi lo usava vede "non attive" nelle Impostazioni al
# prossimo giro invece di credersi coperto.

PROJECT_ID = 'garden-river-conti-febed'
SCOPES     = ['https://www.googleapis.com/auth/cloud-platform']
BASE_FS    = f'https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents'
FCM_URL    = f'https://fcm.googleapis.com/v1/projects/{PROJECT_ID}/messages:send'

sa_info = json.loads(os.environ['FCM_SERVICE_ACCOUNT_JSON'])
creds   = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
creds.refresh(google.auth.transport.requests.Request())
headers = {'Authorization': f'Bearer {creds.token}', 'Content-Type': 'application/json'}


def token_morto(token):
    payload = {
        'validate_only': True,
        'message': {'token': token, 'notification': {'title': 'x', 'body': 'x'}}
    }
    res = requests.post(FCM_URL, headers=headers, json=payload)
    if res.status_code == 200:
        return False
    # FCM segnala un token non più registrato con NOT_FOUND / UNREGISTERED
    corpo = res.text.upper()
    return res.status_code == 404 or 'UNREGISTERED' in corpo


r = requests.get(f'{BASE_FS}/staffTokens', headers=headers)
staff_docs = r.json().get('documents', [])

controllati = 0
rimossi = 0

for doc in staff_docs:
    doc_id = doc['name'].rsplit('/', 1)[-1]
    fields = doc.get('fields', {})
    valori = fields.get('tokens', {}).get('arrayValue', {}).get('values', [])
    tokens = [v['stringValue'] for v in valori if 'stringValue' in v]
    if not tokens:
        continue

    vivi = []
    for tok in tokens:
        controllati += 1
        if token_morto(tok):
            print(f'  Token morto in {doc_id}: {tok[:24]}...')
            rimossi += 1
        else:
            vivi.append(tok)

    if len(vivi) != len(tokens):
        patch = {'fields': {'tokens': {'arrayValue': {
            'values': [{'stringValue': t} for t in vivi]
        }}}}
        pr = requests.patch(
            f'{BASE_FS}/staffTokens/{doc_id}',
            headers=headers, json=patch,
            params={'updateMask.fieldPaths': 'tokens'}
        )
        if pr.status_code != 200:
            print(f'  ERRORE pulizia {doc_id}: {pr.status_code} {pr.text[:200]}')

print(f'Controllati {controllati} token, rimossi {rimossi} non più validi.')
