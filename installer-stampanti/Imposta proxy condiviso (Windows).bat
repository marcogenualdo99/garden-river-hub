@echo off
setlocal
REM Attiva la modalita' "proxy fiscale condiviso" su questo PC Windows.
REM Da lanciare DOPO "Installa (Windows).bat", con "Esegui come amministratore".
REM - genera (o riusa) il token e lo scrive in italretail_config.json
REM - imposta host 0.0.0.0 (ascolto su tutta la rete)
REM - apre la porta 8766 nel firewall (solo rete privata)
REM - riavvia il proxy fiscale
REM Opzionale: se esistono cert/chiave veri (es. win-acme) li usa al posto di quelli locali.
REM   uso:  "Imposta proxy condiviso (Windows).bat" "C:\percorso\fullchain.pem" "C:\percorso\privkey.pem"

net session >nul 2>&1
if errorlevel 1 (
  echo ERRORE: serve "Esegui come amministratore" ^(tasto destro sul file^).
  pause
  exit /b 1
)

set "DEST=%LOCALAPPDATA%\GardenRiverStampanti"
if not exist "%DEST%\proxy_italretail.py" (
  echo ERRORE: proxy non installato. Lancia prima "Installa (Windows).bat".
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Join-Path $env:LOCALAPPDATA 'GardenRiverStampanti\italretail_config.json';" ^
  "$c = if (Test-Path $p) { Get-Content $p -Raw | ConvertFrom-Json } else { [pscustomobject]@{} };" ^
  "function Set-Prop($o,$n,$v){ if ($o.PSObject.Properties[$n]) { $o.$n = $v } else { $o | Add-Member -NotePropertyName $n -NotePropertyValue $v } };" ^
  "if (-not $c.token) { $b = New-Object byte[] 24; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); Set-Prop $c 'token' (([BitConverter]::ToString($b) -replace '-','').ToLower()) };" ^
  "Set-Prop $c 'host' '0.0.0.0';" ^
  "if ('%~1' -ne '' -and '%~2' -ne '') { Set-Prop $c 'cert' '%~1'; Set-Prop $c 'key' '%~2' };" ^
  "[IO.File]::WriteAllText($p, ($c | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)));" ^
  "Write-Host ''; Write-Host 'TOKEN (da mettere in Firestore config/fiscalizzazione):' -ForegroundColor Yellow; Write-Host $c.token -ForegroundColor Green"

netsh advfirewall firewall delete rule name="Garden River proxy fiscale" >nul 2>&1
netsh advfirewall firewall add rule name="Garden River proxy fiscale" dir=in action=allow protocol=TCP localport=8766 profile=private,domain >nul
echo Firewall: porta 8766 aperta (rete privata/dominio).

schtasks /end /tn "GardenRiverProxyItalRetail" >nul 2>&1
schtasks /run /tn "GardenRiverProxyItalRetail" >nul 2>&1
echo Proxy fiscale riavviato in modalita' condivisa.
echo.
echo Prova da un altro dispositivo: https://^<ip-di-questo-pc^>:8766
echo Se la rete di questo PC e' classificata "Pubblica" in Windows, passala a "Privata".
pause
