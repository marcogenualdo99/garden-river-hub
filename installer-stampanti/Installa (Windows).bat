@echo off
setlocal enabledelayedexpansion
REM Installer stampanti Garden River (Windows)
REM Copia i proxy in una cartella stabile e li registra per l'avvio automatico
REM ad ogni login tramite Utilita' di pianificazione (Task Scheduler).

echo Installazione proxy stampanti Garden River...
echo.

set "SRC=%~dp0"
set "DEST=%LOCALAPPDATA%\GardenRiverStampanti"

REM Cerca un interprete Python utilizzabile (pythonw = senza finestra console)
set "PYW="
where pythonw >nul 2>&1 && for /f "delims=" %%P in ('where pythonw') do if not defined PYW set "PYW=%%P"
if not defined PYW (
  where python >nul 2>&1 && for /f "delims=" %%P in ('where python') do if not defined PYW set "PYW=%%P"
)
if not defined PYW (
  echo ERRORE: Python non trovato su questo PC.
  echo Installa Python 3 da https://www.python.org/downloads/windows/
  echo ^(durante l'installazione spunta "Add python.exe to PATH"^) e rilancia questo file.
  pause
  exit /b 1
)
echo Trovato Python: %PYW%

mkdir "%DEST%" >nul 2>&1
copy /Y "%SRC%proxy_stampante.py"   "%DEST%\" >nul
copy /Y "%SRC%proxy_italretail.py"  "%DEST%\" >nul
copy /Y "%SRC%italretail_rt.py"     "%DEST%\" >nul
copy /Y "%SRC%proxy_cert.pem"       "%DEST%\" >nul
copy /Y "%SRC%proxy_key.pem"        "%DEST%\" >nul

call :installa_proxy "GardenRiverProxyStampante"  "proxy_stampante.py"  "8765" "Proxy stampante attivo"
call :installa_proxy "GardenRiverProxyItalRetail" "proxy_italretail.py" "8766" "Proxy ItalRetail attivo"

echo.
echo Fatto. I due proxy partiranno da soli ad ogni accesso a Windows.
echo.
echo IMPORTANTE - passo manuale una tantum su questo PC:
echo   apri il browser e visita una volta ciascuno di questi indirizzi,
echo   accettando l'avviso di certificato non attendibile (e' normale,
echo   e' il certificato locale dei proxy):
echo     https://localhost:8765
echo     https://localhost:8766
echo.
echo Per far fiscalizzare TUTTI i dispositivi dell'ufficio tramite questo PC:
echo   1) apri  %DEST%\italretail_config.json  e aggiungi i campi
echo        "host": "0.0.0.0",  "token": "un-segreto-a-tua-scelta"
echo   2) riavvia l'attivita' GardenRiverProxyItalRetail
echo   3) apri la porta 8766 nel Windows Firewall (connessioni in entrata)
echo   4) segui  FISCALIZZAZIONE-CONDIVISA.md  per Firestore e i certificati
echo.
pause
exit /b 0

:installa_proxy
REM %1=nome attivita' pianificata  %2=script  %3=porta  %4=firma attesa nella risposta HTTP
set "TASKNAME=%~1"
set "SCRIPT=%~2"
set "PORTA=%~3"
set "FIRMA=%~4"
set "SALTA="

REM Se l'attivita' esiste gia' (installazione precedente di questo stesso
REM installer), e' un aggiornamento: la ricreiamo senza controllare la porta,
REM tanto e' occupata dalla nostra stessa attivita' che stiamo per sostituire.
REM Altrimenti (prima installazione) controlliamo che la porta sia libera,
REM per non duplicare un proxy gia' presente su questa postazione (es.
REM installato in passato con un altro nome) ed evitare conflitti.
schtasks /query /tn "%TASKNAME%" >nul 2>&1
if !errorlevel! neq 0 (
  netstat -ano | findstr /r /c:":%PORTA% .*LISTENING" >nul 2>&1
  if !errorlevel! equ 0 (
    set "OK_ESISTENTE="
    where curl >nul 2>&1
    if not errorlevel 1 (
      for /f "delims=" %%R in ('curl -sk --max-time 3 "https://localhost:%PORTA%" 2^>nul') do (
        echo %%R | findstr /c:"%FIRMA%" >nul && set "OK_ESISTENTE=1"
      )
    )
    if defined OK_ESISTENTE (
      echo  - porta %PORTA% gia' coperta da un proxy funzionante: non installo %TASKNAME% per evitare un duplicato
    ) else (
      echo  ATTENZIONE: la porta %PORTA% e' occupata da un altro programma non riconosciuto.
      echo    Non installo %TASKNAME% per evitare conflitti. Libera la porta %PORTA% e rilancia l'installer se necessario.
    )
    set "SALTA=1"
  )
)

if not defined SALTA (
  schtasks /create /tn "%TASKNAME%" /tr "\"%PYW%\" \"%DEST%\%SCRIPT%\"" /sc onlogon /rl highest /f >nul
  echo  - Attivita' pianificata %TASKNAME% creata/aggiornata (avvio al login)
  schtasks /run /tn "%TASKNAME%" >nul 2>&1
)
goto :eof
