# Validazione DNS-01 per win-acme tramite acme-dns (auth.acme-dns.io).
# Uso (chiamato da wacs.exe):  acme-dns-validate.ps1 create <dominio> <record> <token>
#                              acme-dns-validate.ps1 delete <dominio> <record> <token>
# Le credenziali stanno in acme-dns-cassa.json (NON in git, mai stampate qui).
param([string]$Azione, [string]$Dominio, [string]$Record, [string]$Token)

$ErrorActionPreference = 'Stop'
if ($Azione -ne 'create') { exit 0 }   # acme-dns tiene un solo TXT: niente da cancellare

$file = Join-Path $PSScriptRoot 'acme-dns-cassa.json'
$j = Get-Content $file -Raw | ConvertFrom-Json
# Accetta sia { username, password, subdomain } sia { "<dominio>": { ... } } (acme-dns-client)
if (-not $j.username) {
  $voce = $j.PSObject.Properties | Where-Object { $_.Value.username } | Select-Object -First 1
  if ($voce) { $j = $voce.Value }
}
if (-not ($j.username -and $j.password -and $j.subdomain)) { throw 'acme-dns-cassa.json: servono username, password, subdomain' }

$server = if ($j.server) { $j.server.TrimEnd('/') } else { 'https://auth.acme-dns.io' }
$corpo = @{ subdomain = $j.subdomain; txt = $Token } | ConvertTo-Json -Compress
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-RestMethod -Method Post -Uri "$server/update" -ContentType 'application/json' `
  -Headers @{ 'X-Api-User' = $j.username; 'X-Api-Key' = $j.password } -Body $corpo | Out-Null
Write-Host "acme-dns: TXT aggiornato per $Record"
Start-Sleep -Seconds 5
