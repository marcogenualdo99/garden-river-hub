# Eseguito da win-acme dopo ogni rinnovo: riavvia il proxy fiscale cosi' carica il nuovo certificato.
schtasks /end /tn "GardenRiverProxyItalRetail" | Out-Null
Start-Sleep -Seconds 2
schtasks /run /tn "GardenRiverProxyItalRetail" | Out-Null
Write-Host "Proxy fiscale riavviato dopo il rinnovo del certificato."
