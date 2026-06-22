# ── Invia FCM a tutti i token ─────────────────────────────────────────────
almeno_uno_ok = False
for tok in fcm_tokens:
    payload = {
        'message': {
            'token': tok,
            'data': {
                'title': 'MANUTENZIONE',
                'body': f'Nuovo ticket: {doc_data.get("unit", "?")} — {doc_data.get("category", "?")}',
                'url': '/manutenzione/'
            }
        }
    }
    res = requests.post(FCM_URL, headers=headers, json=payload)
    if res.status_code == 200:
        print(f'    OK → {tok[:24]}...')
        almeno_uno_ok = True
    else:
        print(f'    ERRORE {res.status_code} → {res.text[:300]}')

# ── Marca il ticket come notificato solo se almeno un invio è riuscito ────
if almeno_uno_ok:
    patch_url = f'{BASE_FS}/maintenance_tickets/{doc_id}?updateMask.fieldPaths=notified'
    requests.patch(patch_url, headers=headers, json={
        'fields': {'notified': {'booleanValue': True}}
    })
else:
    print(f'  ⚠ Nessun token valido — ticket NON marcato come notificato, verrà riprovato.')
