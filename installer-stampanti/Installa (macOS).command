#!/bin/bash
# Installer stampanti Garden River (macOS)
# Copia i proxy in una cartella stabile e li registra per l'avvio automatico
# ad ogni login, cosi' non serve piu' cliccare i file .command a mano.
set -e
cd "$(dirname "$0")"

DEST="$HOME/Library/Application Support/GardenRiverStampanti"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
PY="/usr/bin/python3"

echo "Installazione proxy stampanti Garden River..."

if [ ! -x "$PY" ]; then
  echo "ERRORE: $PY non trovato. Serve Python 3 installato su questo Mac."
  exit 1
fi

mkdir -p "$DEST"
mkdir -p "$LAUNCH_AGENTS"
cp -f proxy_stampante.py proxy_italretail.py italretail_rt.py proxy_cert.pem proxy_key.pem "$DEST/"

write_plist () {
  local label="$1"
  local script="$2"
  local porta="$3"
  local firma="$4"   # stringa nella risposta HTTP che identifica IL NOSTRO proxy su quella porta
  local plist="$LAUNCH_AGENTS/$label.plist"

  # Se non e' un aggiornamento di un nostro LaunchAgent gia' installato (il caso
  # normale di ri-lancio dell'installer), controlla che la porta sia libera prima
  # di crearne uno nuovo: evita di duplicare un proxy gia' presente su questa
  # postazione (es. installato a mano in passato con un altro nome) e andare in
  # crash-loop per conflitto di porta.
  if [ ! -f "$plist" ] && lsof -nP -iTCP:"$porta" -sTCP:LISTEN >/dev/null 2>&1; then
    local risposta
    risposta=$(curl -sk --max-time 3 "https://localhost:$porta" 2>/dev/null || true)
    if echo "$risposta" | grep -q "$firma"; then
      echo "  - porta $porta gia' coperta da un proxy funzionante (probabilmente installato in precedenza con un altro nome): non installo $label per evitare un duplicato"
    else
      echo "  ATTENZIONE: la porta $porta e' occupata da un altro programma non riconosciuto (non risponde come atteso)."
      echo "    Non installo $label per evitare conflitti. Libera la porta $porta e rilancia l'installer se necessario."
    fi
    return 0
  fi

  local env_block="$5"   # opzionale: blocco <key>EnvironmentVariables</key>...

  cat > "$plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>$DEST/$script</string>
  </array>
  <key>WorkingDirectory</key><string>$DEST</string>
$env_block
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$DEST/$label.log</string>
  <key>StandardErrorPath</key><string>$DEST/$label.log</string>
</dict>
</plist>
PLIST
  # Ricarica se gia' presente (aggiornamento), altrimenti carica per la prima volta
  launchctl unload "$plist" >/dev/null 2>&1 || true
  launchctl load -w "$plist"
  echo "  - $label avviato (log: $DEST/$label.log)"
}

write_plist "it.gardenriver.proxystampante" "proxy_stampante.py" "8765" "Proxy stampante attivo"

# ── Modalita' del proxy ItalRetail: solo locale, oppure condiviso in ufficio ──
echo ""
echo "PROXY REGISTRATORE TELEMATICO (scontrini fiscali)"
echo "  1) Solo locale  — solo QUESTO computer puo' fiscalizzare (default)"
echo "  2) Condiviso     — tutti i dispositivi dell'ufficio possono fiscalizzare,"
echo "                     tramite questo computer (che deve restare acceso)"
read -p "Scegli [1/2] (INVIO = 1): " MODO_ITALRETAIL

ENV_ITALRETAIL=""
if [ "$MODO_ITALRETAIL" = "2" ]; then
  read -p "  Token condiviso (INVIO = generane uno nuovo): " TOKEN_ITALRETAIL
  if [ -z "$TOKEN_ITALRETAIL" ]; then
    TOKEN_ITALRETAIL=$(/usr/bin/python3 -c "import secrets; print(secrets.token_urlsafe(24))")
    echo "  Token generato: $TOKEN_ITALRETAIL"
  fi
  ENV_ITALRETAIL="  <key>EnvironmentVariables</key>
  <dict>
    <key>PROXY_HOST</key><string>0.0.0.0</string>
    <key>ITALRETAIL_TOKEN</key><string>$TOKEN_ITALRETAIL</string>
  </dict>"
  IP_LAN=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "<ip-di-questo-mac>")
  echo ""
  echo "  ► Da fare UNA VOLTA nella console Firebase (progetto garden-river-conti-febed):"
  echo "    crea il documento  config/fiscalizzazione  con i campi:"
  echo "        proxy_url  (string) =  https://$IP_LAN:8766"
  echo "        token      (string) =  $TOKEN_ITALRETAIL"
  echo ""
  echo "  ► Assicurati che questo Mac abbia un IP fisso sulla rete e che il"
  echo "    firewall consenta le connessioni in entrata sulla porta 8766."
fi

write_plist "it.gardenriver.proxyitalretail" "proxy_italretail.py" "8766" "Proxy ItalRetail attivo" "$ENV_ITALRETAIL"

echo ""
echo "Fatto. I proxy partiranno da soli ad ogni login."
echo ""
echo "IMPORTANTE - passo manuale una tantum su OGNI dispositivo che stampa/fiscalizza:"
echo "  apri il browser e visita una volta ciascuno di questi indirizzi,"
echo "  accettando l'avviso di certificato non attendibile (e' normale):"
echo "    https://localhost:8765            (proxy stampante, solo su questo Mac)"
if [ "$MODO_ITALRETAIL" = "2" ]; then
  echo "    https://$IP_LAN:8766             (proxy fiscale condiviso, da OGNI dispositivo)"
else
  echo "    https://localhost:8766           (proxy fiscale, solo su questo Mac)"
fi
echo ""
read -p "Premi INVIO per chiudere..."
