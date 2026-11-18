// Gestione unica delle stampanti termiche della suite Garden River.
//
// Le stampanti si configurano UNA volta dalla Hub (Impostazioni > Stampanti) e
// vivono su Firestore, collezione `stampanti`:
//   { nome, tipo: 'epson' | 'sunmi', ip, servizi: ['conti', 'comande'], attiva }
// Ogni app chiede solo "stampa questo per il servizio X": la stampante e il
// canale di invio si decidono qui. Chi ha il modulo del servizio sbloccato nei
// permessi (Conti, Ristorazione...) puo' stampare sulla stampante associata.
//
// Canali di invio (oggi, lato browser):
//   - epson : HTTPS diretta alla stampante (ePOS-Print), serve il certificato
//   - sunmi : proxy locale https://localhost:8765/sunmi (proxy_stampante.py),
//             che traduce in ESC/POS e inoltra alla porta 9100
// Quando ci sara' un dispositivo di sede sempre acceso, si aggiunge qui il
// canale "coda" (lavori su Firestore letti dall'agente): le app non cambiano.
//
// Richiede window._fb (db, collection, doc, setDoc, deleteDoc, onSnapshot).
(function () {
  'use strict';

  // Servizi di stampa disponibili. `modulo` = modulo della Hub che li usa.
  var SERVIZI = [
    { id: 'conti',   nome: 'Conti pensioni (conto e riepilogo)', modulo: 'conti' },
    { id: 'comande', nome: 'Comande ristorazione',               modulo: 'ristorazione' },
  ];
  var TIPI = [
    { id: 'epson', nome: 'Epson (ePOS, diretta in rete)' },
    { id: 'sunmi', nome: 'Sunmi / ESC-POS (tramite proxy locale)' },
  ];
  var PROXY = 'https://localhost:8765';
  var CACHE_KEY = 'gr_stampanti_cache';

  var elenco = [];
  var avviato = false;
  var primaLettura = null;     // promessa risolta alla prima lettura da Firestore
  var risolviPrima = function () {};

  try { elenco = JSON.parse(localStorage.getItem(CACHE_KEY) || '[]') || []; } catch (e) { elenco = []; }

  function salvaCache() {
    try { localStorage.setItem(CACHE_KEY, JSON.stringify(elenco)); } catch (e) { /* ok */ }
  }

  function attendiFirebase() {
    return new Promise(function (resolve) {
      if (window._fbReady) return resolve();
      window.addEventListener('firebase-ready', function () { resolve(); }, { once: true });
    });
  }

  // Segue in tempo reale l'elenco stampanti e tiene una copia in cache, cosi'
  // le app funzionano anche se Firestore e' lento o offline.
  function avvia() {
    if (avviato) return;
    avviato = true;
    primaLettura = new Promise(function (r) { risolviPrima = r; });
    attendiFirebase().then(function () {
      var fb = window._fb;
      fb.onSnapshot(fb.collection(fb.db, 'stampanti'), function (snap) {
        elenco = snap.docs.map(function (d) { return Object.assign({ id: d.id }, d.data()); });
        salvaCache();
        window.dispatchEvent(new Event('stampanti-aggiornate'));
        risolviPrima();
      }, function (err) { console.error('Errore lettura stampanti:', err); risolviPrima(); });
    });
  }

  function lista() { return elenco.slice(); }

  // Stampante attiva associata a un servizio (la prima in ordine di nome).
  function per(servizio) {
    var trovate = elenco.filter(function (p) {
      return p.attiva !== false && (p.servizi || []).indexOf(servizio) !== -1;
    }).sort(function (a, b) { return String(a.nome || '').localeCompare(String(b.nome || ''), 'it'); });
    return trovate[0] || null;
  }

  // Compatibilita': finche' non c'e' nessuna stampante configurata dalla Hub si
  // usa l'impostazione vecchia salvata sul singolo dispositivo.
  function legacy() {
    return {
      id: '_legacy',
      nome: 'Stampante del dispositivo',
      tipo: localStorage.getItem('printer_tipo') || 'epson',
      ip: localStorage.getItem('epson_printer_ip') || '192.168.1.5',
    };
  }

  function esito(ok, err) { return { ok: ok, err: err || '' }; }

  async function inviaEpson(p, xml) {
    var url = 'https://' + p.ip + '/cgi-bin/epos/service.cgi?devid=local_printer&timeout=10000';
    try {
      var r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'text/xml; charset=utf-8', 'SOAPAction': '""' },
        body: xml,
      });
      if (!r.ok) return esito(false, 'HTTP ' + r.status);
      var text = await r.text();
      var code = (text.match(/code="([^"]*)"/) || [])[1] || '';
      return esito(text.indexOf('success="true"') !== -1, code);
    } catch (e) {
      return esito(false, 'stampante non raggiungibile (' + p.ip + ')');
    }
  }

  async function inviaSunmi(p, xml) {
    try {
      var r = await fetch(PROXY + '/sunmi?ip=' + encodeURIComponent(p.ip), {
        method: 'POST',
        headers: { 'Content-Type': 'text/xml; charset=utf-8' },
        body: xml,
      });
      var text = await r.text();
      if (!r.ok) return esito(false, 'Proxy stampante: ' + (text || 'HTTP ' + r.status));
      return esito(text.indexOf('success="true"') !== -1, '');
    } catch (e) {
      return esito(false, 'proxy stampante non raggiungibile su questo dispositivo (avvia il proxy e apri ' + PROXY + ' una volta)');
    }
  }

  // Invia direttamente a una stampante precisa.
  function inviaA(p, xml) {
    if (!p || !p.ip) return Promise.resolve(esito(false, 'IP della stampante non impostato'));
    return p.tipo === 'sunmi' ? inviaSunmi(p, xml) : inviaEpson(p, xml);
  }

  // Invia per servizio: sceglie la stampante associata (o quella del dispositivo).
  async function invia(servizio, xml) {
    // Se l'elenco non e' ancora arrivato da Firestore (e non c'e' cache) attendi un attimo
    if (!elenco.length && primaLettura) {
      await Promise.race([primaLettura, new Promise(function (r) { setTimeout(r, 2500); })]);
    }
    var p = per(servizio) || (elenco.length ? null : legacy());
    if (!p) return esito(false, 'Nessuna stampante associata al servizio "' + servizio + '". Configurala da Hub > Impostazioni > Stampanti.');
    return inviaA(p, xml);
  }

  function xmlProva(nome) {
    return '<?xml version="1.0" encoding="utf-8"?>' +
      '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>' +
      '<epos-print xmlns="http://www.epson-pos.com/schemas/2011/03/epos-print">' +
      '<text font="font_a" align="center" height="2" width="2">TEST OK</text><text>&#10;</text>' +
      '<text align="center" height="1" width="1">' + String(nome || '').replace(/[<&>]/g, '') + '</text><text>&#10;</text>' +
      '<text align="center">Garden River · accenti: è é à ù ò ì €</text><text>&#10;&#10;&#10;</text>' +
      '<cut type="feed"/></epos-print></s:Body></s:Envelope>';
  }

  function prova(p) { return inviaA(p, xmlProva(p && p.nome)); }

  // Controlla se il proxy locale e' attivo su questo dispositivo.
  async function proxyAttivo() {
    try { var r = await fetch(PROXY + '/', { method: 'GET' }); return r.ok; } catch (e) { return false; }
  }

  // --- gestione (usata dalla pagina Stampanti della Hub) ---
  function nuovoId() { return 'p_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 5); }

  async function salva(p) {
    var fb = window._fb;
    var id = p.id || nuovoId();
    var dati = {
      nome: String(p.nome || '').trim(),
      tipo: p.tipo === 'sunmi' ? 'sunmi' : 'epson',
      ip: String(p.ip || '').trim(),
      servizi: (p.servizi || []).filter(function (s) { return SERVIZI.some(function (x) { return x.id === s; }); }),
      attiva: p.attiva !== false,
    };
    await fb.setDoc(fb.doc(fb.db, 'stampanti', id), dati);
    return id;
  }

  async function elimina(id) {
    var fb = window._fb;
    await fb.deleteDoc(fb.doc(fb.db, 'stampanti', id));
  }

  window.GRStampanti = {
    SERVIZI: SERVIZI, TIPI: TIPI,
    avvia: avvia, lista: lista, per: per,
    invia: invia, inviaA: inviaA, prova: prova, proxyAttivo: proxyAttivo,
    salva: salva, elimina: elimina,
  };
})();
