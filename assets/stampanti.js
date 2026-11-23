// Gestione unica delle stampanti termiche della suite Garden River.
//
// Le stampanti si configurano UNA volta dalla Hub (Impostazioni > Stampanti) e
// vivono su Firestore, collezione `stampanti`:
//   { nome, tipo: 'epson' | 'sunmi', ip, servizi: ['conti', 'comande'], auto: ['comande_pranzo'], attiva }
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
    { id: 'shop',    nome: 'Ordini shop',                        modulo: 'shop' },
    { id: 'mense',   nome: 'Report mense scolastiche',           modulo: 'mense' },
  ];
  // Stampe automatiche: ogni stampante sceglie quali fa (devono appartenere a un suo servizio).
  var AUTO = [
    { id: 'comande_pranzo', servizio: 'comande', nome: 'Comande pranzo' },
    { id: 'comande_cena',   servizio: 'comande', nome: 'Comande cena' },
    { id: 'shop',           servizio: 'shop',    nome: 'Ordini shop appena arrivano' },
  ];
  var TIPI = [
    { id: 'epson', nome: 'Epson (ePOS, diretta in rete)' },
    { id: 'sunmi', nome: 'Sunmi / ESC-POS (tramite proxy locale)' },
    { id: 'interna', nome: 'Sunmi V2 integrata (solo dall\'app Garden Hub sul V2)' },
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

  // Stampanti attive tra cui scegliere per stampare a mano un servizio: solo quelle
  // associate al servizio (se nessuna lo e', tutte le attive, come prima).
  function candidatePer(servizio) {
    var ord = function (a, b) { return String(a.nome || '').localeCompare(String(b.nome || ''), 'it'); };
    var attive = elenco.filter(function (p) { return p.attiva !== false; }).sort(ord);
    var assoc = attive.filter(function (p) { return (p.servizi || []).indexOf(servizio) !== -1; });
    return assoc.length ? assoc : attive;
  }

  // Stampanti che fanno una stampa automatica (id di AUTO). Se nessuna e' stata
  // configurata si usa la stampante associata al servizio, come prima.
  function perAuto(autoId) {
    var def = AUTO.filter(function (a) { return a.id === autoId; })[0];
    var trovate = elenco.filter(function (p) {
      return p.attiva !== false && (p.auto || []).indexOf(autoId) !== -1 && (!def || (p.servizi || []).indexOf(def.servizio) !== -1);
    }).sort(function (a, b) { return String(a.nome || '').localeCompare(String(b.nome || ''), 'it'); });
    if (trovate.length) return trovate;
    var p = def && per(def.servizio);
    return p ? [p] : [];
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
    var ac = new AbortController();
    var tm = setTimeout(function () { ac.abort(); }, 12000);
    try {
      var r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'text/xml; charset=utf-8', 'SOAPAction': '""' },
        body: xml,
        signal: ac.signal,
      });
      clearTimeout(tm);
      if (!r.ok) return esito(false, 'HTTP ' + r.status);
      var text = await r.text();
      var code = (text.match(/code="([^"]*)"/) || [])[1] || '';
      return esito(text.indexOf('success="true"') !== -1, code);
    } catch (e) {
      clearTimeout(tm);
      if (ac.signal.aborted) return esito(false, 'nessuna risposta da ' + (p.nome || p.ip) + ' (' + p.ip + '): controlla che sia accesa e sulla stessa rete');
      // Stampante non raggiungibile da questo dispositivo (altra rete, certificato): la stampa il V2 dalla coda
      return inviaCoda(p, xml);
    }
  }

  // Dentro l'app Garden Hub del Sunmi (WebView) la stampa e' diretta, senza proxy ne' coda.
  var nativoCb = {};
  window.__grNativoRis = function (id, ok, err) {
    var f = nativoCb[id];
    if (f) { delete nativoCb[id]; f(ok ? esito(true, '') : esito(false, err)); }
  };
  function inviaNativo(p, xml) {
    return new Promise(function (resolve) {
      var id = 'n' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
      var tm = setTimeout(function () { delete nativoCb[id]; resolve(esito(false, 'nessuna risposta da ' + (p.nome || p.ip) + ' (' + p.ip + ')')); }, 15000);
      nativoCb[id] = function (r) { clearTimeout(tm); resolve(r); };
      try { window.GRNativo.stampa(id, p.ip, xml); }
      catch (e) { clearTimeout(tm); delete nativoCb[id]; resolve(esito(false, 'app nativa non disponibile')); }
    });
  }

  // Stampante integrata del V2: esiste solo dentro l'app Garden Hub installata sul V2.
  function inviaInterna(p, xml) {
    if (window.GRNativo && window.GRNativo.stampa) return inviaNativo(p, xml);
    // Fuori dall'app (iPad, telefono, PC, anche da un'altra rete): passa dalla coda, la stampa il V2
    return inviaCoda(p, xml);
  }

  async function inviaSunmi(p, xml) {
    if (window.GRNativo && window.GRNativo.stampa) return inviaNativo(p, xml);
    var ac = new AbortController();
    var tm = setTimeout(function () { ac.abort(); }, 20000);
    try {
      var r = await fetch(PROXY + '/sunmi?ip=' + encodeURIComponent(p.ip), {
        method: 'POST',
        headers: { 'Content-Type': 'text/xml; charset=utf-8' },
        body: xml,
        signal: ac.signal,
      });
      clearTimeout(tm);
      var text = await r.text();
      if (!r.ok) return esito(false, 'Proxy stampante: ' + (text || 'HTTP ' + r.status));
      return esito(text.indexOf('success="true"') !== -1, '');
    } catch (e) {
      clearTimeout(tm);
      if (ac.signal.aborted) return esito(false, 'nessuna risposta da ' + (p.nome || p.ip) + ' (' + p.ip + ')');
      // Nessun proxy su questo dispositivo (iPad/iPhone...): passa dalla coda, la stampa l'agente di sede
      return inviaCoda(p, xml);
    }
  }

  // Canale "coda": il lavoro va su Firestore `coda_stampa`, lo stampa l'app Agente Stampa
  // (Sunmi di sede) tramite la Cloud Function stampa-agente. Attende l'esito (max 30 s).
  async function inviaCoda(p, xml) {
    var fb = window._fb;
    var errNoProxy = 'proxy stampante non raggiungibile su questo dispositivo e agente di stampa non risponde';
    var passo = 'scrittura in coda';
    try {
      var id = 'j_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
      var ref = fb.doc(fb.db, 'coda_stampa', id);
      await fb.setDoc(ref, { stato: 'in_coda', ip: p.ip, dispositivo: p.dispositivo || '', xml: xml, stampante: p.nome || p.ip, creato_ts: Date.now() / 1000 });
      passo = 'attesa del V2';
      return await new Promise(function (resolve) {
        var unsub = null, fatto = false;
        function fine(r) { if (fatto) return; fatto = true; clearTimeout(tm); if (unsub) unsub(); resolve(r); }
        var tm = setTimeout(function () { fine(esito(false, errNoProxy + ' [nessuna presa in carico dal V2 in 30 s: controlla token e funzione]')); }, 30000);
        unsub = fb.onSnapshot(ref, function (snap) {
          var d = snap.exists() ? snap.data() : null;
          if (!d) return;
          if (d.stato === 'ok') fine(esito(true, ''));
          else if (d.stato === 'fallita') fine(esito(false, d.errore || 'stampa fallita'));
          else if (d.stato === 'scaduta') fine(esito(false, 'lavoro scaduto in coda (il V2 non l\'ha preso in tempo)'));
        }, function (e) { fine(esito(false, 'lettura esito negata: ' + (e && e.code))); });
      });
    } catch (e) {
      return esito(false, 'coda di stampa, ' + passo + ': ' + ((e && (e.code || e.message)) || 'errore') + (passo === 'scrittura in coda' ? ' (regola Firestore coda_stampa non pubblicata o accesso non valido)' : ''));
    }
  }

  // Invia direttamente a una stampante precisa.
  function inviaA(p, xml) {
    if (!p || !p.ip) return Promise.resolve(esito(false, 'IP della stampante non impostato'));
    return (p.tipo === 'interna' ? inviaInterna(p, xml) : p.tipo === 'sunmi' ? inviaSunmi(p, xml) : inviaEpson(p, xml)).then(function (r) { r.stampante = p.nome || p.ip; return r; });
  }

  // Ultima stampante scelta a mano per servizio, su questo dispositivo.
  function ultimaScelta(servizio) { try { return localStorage.getItem('gr_stampante_scelta_' + servizio) || ''; } catch (e) { return ''; } }
  function ricordaScelta(servizio, id) { try { localStorage.setItem('gr_stampante_scelta_' + servizio, id); } catch (e) { /* ok */ } }

  // Finestra "Su quale stampante?": risolve con la stampante scelta o null se annullata.
  function sceglieStampante(servizio, candidate) {
    return new Promise(function (resolve) {
      var pre = ultimaScelta(servizio);
      if (!candidate.some(function (p) { return p.id === pre; })) {
        var assoc = per(servizio);
        pre = assoc ? assoc.id : candidate[0].id;
      }
      var ov = document.createElement('div');
      ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:99999;display:flex;align-items:center;justify-content:center;padding:16px;font-family:inherit';
      var box = document.createElement('div');
      box.style.cssText = 'background:#fff;color:#1c1c1c;border-radius:14px;max-width:360px;width:100%;padding:18px;box-shadow:0 10px 40px rgba(0,0,0,.3)';
      var h = document.createElement('div');
      h.style.cssText = 'font-weight:700;font-size:16px;margin-bottom:10px';
      h.textContent = 'Su quale stampante?';
      box.appendChild(h);
      var scelta = pre;
      var righe = [];
      candidate.forEach(function (p) {
        var b = document.createElement('button');
        b.type = 'button';
        b.style.cssText = 'display:block;width:100%;text-align:left;padding:11px 12px;margin-bottom:8px;border-radius:10px;border:2px solid #d9d9d9;background:#fff;font:inherit;cursor:pointer';
        b.innerHTML = '<div style="font-weight:600"></div><div style="font-size:12px;color:#777"></div>';
        b.firstChild.textContent = p.nome || 'Stampante';
        var t = (p.tipo === 'interna' ? 'Sunmi V2 integrata' : (p.tipo === 'sunmi' ? 'Sunmi' : 'Epson') + ' · ' + (p.ip || ''));
        b.lastChild.textContent = t;
        b.onclick = function () { scelta = p.id; evidenzia(); };
        righe.push({ id: p.id, b: b });
        box.appendChild(b);
      });
      function evidenzia() { righe.forEach(function (r) { r.b.style.borderColor = r.id === scelta ? '#2f7d32' : '#d9d9d9'; }); }
      evidenzia();
      var az = document.createElement('div');
      az.style.cssText = 'display:flex;gap:8px;margin-top:6px';
      var ann = document.createElement('button');
      ann.type = 'button'; ann.textContent = 'Annulla';
      ann.style.cssText = 'flex:1;padding:11px;border-radius:10px;border:1px solid #ccc;background:#f4f4f4;font:inherit;cursor:pointer';
      var ok = document.createElement('button');
      ok.type = 'button'; ok.textContent = 'Stampa';
      ok.style.cssText = 'flex:1;padding:11px;border-radius:10px;border:0;background:#2f7d32;color:#fff;font:inherit;font-weight:700;cursor:pointer';
      function chiudi(r) { document.body.removeChild(ov); resolve(r); }
      ann.onclick = function () { chiudi(null); };
      ok.onclick = function () { var p = candidate.filter(function (x) { return x.id === scelta; })[0] || null; chiudi(p); };
      ov.onclick = function (e) { if (e.target === ov) chiudi(null); };
      az.appendChild(ann); az.appendChild(ok); box.appendChild(az); ov.appendChild(box);
      document.body.appendChild(ov);
    });
  }

  // Invia per servizio: sceglie la stampante associata (o quella del dispositivo).
  // Con opts.scegli (stampe manuali) e piu' stampanti attive chiede su quale stampare.
  async function invia(servizio, xml, opts) {
    // Se l'elenco non e' ancora arrivato da Firestore (e non c'e' cache) attendi un attimo
    if (!elenco.length && primaLettura) {
      await Promise.race([primaLettura, new Promise(function (r) { setTimeout(r, 2500); })]);
    }
    if (opts && opts.auto) {
      var dest = perAuto(opts.auto);
      if (!dest.length) return esito(false, 'Nessuna stampante associata al servizio "' + servizio + '". Configurala da Hub > Impostazioni > Stampanti.');
      var ris = await Promise.all(dest.map(function (d) { return inviaA(d, xml); }));
      var ko = ris.filter(function (r) { return !r.ok; });
      var tot = esito(!ko.length, ko.map(function (r) { return r.stampante + ': ' + (r.err || 'errore'); }).join(' | '));
      tot.stampante = dest.map(function (d) { return d.nome || d.ip; }).join(', ');
      return tot;
    }
    var p = per(servizio) || (elenco.length ? null : legacy());
    if (opts && opts.scegli) {
      var attive = candidatePer(servizio);
      if (attive.length > 1) {
        var scelta = await sceglieStampante(servizio, attive);
        if (!scelta) { var r = esito(false, ''); r.annullata = true; return r; }
        ricordaScelta(servizio, scelta.id);
        p = scelta;
      }
    }
    if (!p) return esito(false, 'Nessuna stampante associata al servizio "' + servizio + '". Configurala da Hub > Impostazioni > Stampanti.');
    return inviaA(p, xml);
  }

  function xmlProva(nome, logo) {
    return '<?xml version="1.0" encoding="utf-8"?>' +
      '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>' +
      '<epos-print xmlns="http://www.epson-pos.com/schemas/2011/03/epos-print">' + (logo || '') +
      '<text font="font_a" align="center" height="2" width="2">TEST OK</text><text>&#10;</text>' +
      '<text align="center" height="1" width="1">' + String(nome || '').replace(/[<&>]/g, '') + '</text><text>&#10;</text>' +
      '<text align="center">Garden River · accenti: è é à ù ò ì €</text><text>&#10;&#10;&#10;</text>' +
      '<cut type="feed"/></epos-print></s:Body></s:Envelope>';
  }

  async function prova(p) {
    var logo = await logoPerStampa('prova');
    return inviaA(p, xmlProva(p && p.nome, logo));
  }

  // Controlla se il proxy locale e' attivo su questo dispositivo.
  async function proxyAttivo() {
    if (window.GRNativo) return true;
    try { var r = await fetch(PROXY + '/', { method: 'GET' }); return r.ok; } catch (e) { return false; }
  }

  // --- gestione (usata dalla pagina Stampanti della Hub) ---
  function nuovoId() { return 'p_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 5); }

  async function salva(p) {
    var fb = window._fb;
    var id = p.id || nuovoId();
    var dati = {
      nome: String(p.nome || '').trim(),
      tipo: p.tipo === 'sunmi' || p.tipo === 'interna' ? p.tipo : 'epson',
      ip: p.tipo === 'interna' ? 'interna' : String(p.ip || '').trim(),
      dispositivo: p.tipo === 'interna' ? String(p.dispositivo || '').trim() : '',
      servizi: (p.servizi || []).filter(function (s) { return SERVIZI.some(function (x) { return x.id === s; }); }),
      attiva: p.attiva !== false,
    };
    dati.auto = (p.auto || []).filter(function (a) {
      return AUTO.some(function (x) { return x.id === a && dati.servizi.indexOf(x.servizio) !== -1; });
    });
    await fb.setDoc(fb.doc(fb.db, 'stampanti', id), dati);
    return id;
  }

  async function elimina(id) {
    var fb = window._fb;
    await fb.deleteDoc(fb.doc(fb.db, 'stampanti', id));
  }


  // ── Stampe automatiche ─────────────────────────────────────────────────────
  // Configurazione unica (Hub > Impostazioni > Stampanti > Stampe automatiche) in
  // Firestore impostazioni/stampa_automatica:
  //   comande: { pranzo: {attivo, ora:'11:30'}, cena: {attivo, ora:'18:00'} }
  //   shop:    { attiva, attivo_dal: ISO }   (stampa all'arrivo dell'ordine)
  // Le stampe partono dal primo dispositivo che ha aperta la pagina giusta
  // (Ristorazione o Shop); "rivendica" evita che due dispositivi stampino la stessa cosa.
  var AUTO_DEFAULT = {
    comande: { pranzo: { attivo: false, ora: '11:30' }, cena: { attivo: false, ora: '18:00' } },
    shop: { attiva: false, attivo_dal: '' },
    aspetto: { logo: 'conti' },   // logo sulle stampe: 'conti' (tutto tranne le comande) | 'tutte' | 'mai'
  };
  var autoCfg = JSON.parse(JSON.stringify(AUTO_DEFAULT));
  var autoAvviato = false;
  try {
    var _c = JSON.parse(localStorage.getItem('gr_stampa_auto_cfg') || 'null');
    if (_c) autoCfg = unisciCfg(_c);
  } catch (e) { /* ok */ }

  function unisciCfg(c) {
    c = c || {};
    var cm = c.comande || {}, d = AUTO_DEFAULT;
    function fascia(k) { var x = cm[k] || {}; return { attivo: x.attivo === true, ora: /^\d{1,2}:\d{2}$/.test(x.ora || '') ? x.ora : d.comande[k].ora }; }
    var sh = c.shop || {};
    var lg = (c.aspetto || {}).logo;
    return { comande: { pranzo: fascia('pranzo'), cena: fascia('cena') },
             shop: { attiva: sh.attiva === true, attivo_dal: sh.attivo_dal || '' },
             aspetto: { logo: lg === 'tutte' || lg === 'mai' ? lg : 'conti' } };
  }

  function avviaAuto() {
    if (autoAvviato) return;
    autoAvviato = true;
    attendiFirebase().then(function () {
      var fb = window._fb;
      fb.onSnapshot(fb.doc(fb.db, 'impostazioni', 'stampa_automatica'), function (snap) {
        autoCfg = unisciCfg(snap.exists() ? snap.data() : null);
        try { localStorage.setItem('gr_stampa_auto_cfg', JSON.stringify(autoCfg)); } catch (e) { /* ok */ }
        window.dispatchEvent(new Event('stampa-auto-aggiornata'));
      }, function (err) { console.error('Errore lettura stampa automatica:', err); });
    });
  }

  async function salvaAuto(cfg) {
    var fb = window._fb;
    var nuovo = unisciCfg(cfg);
    // "attivo_dal": da quando si stampano gli ordini shop (niente ordini vecchi)
    if (nuovo.shop.attiva && !autoCfg.shop.attiva) nuovo.shop.attivo_dal = new Date().toISOString();
    else if (nuovo.shop.attiva) nuovo.shop.attivo_dal = autoCfg.shop.attivo_dal || new Date().toISOString();
    await fb.setDoc(fb.doc(fb.db, 'impostazioni', 'stampa_automatica'), nuovo);
  }

  function idDispositivo() {
    var id = localStorage.getItem('gr_device_id');
    if (!id) { id = 'd_' + Math.random().toString(36).slice(2, 10); try { localStorage.setItem('gr_device_id', id); } catch (e) { /* ok */ } }
    return id;
  }

  // Prenota una stampa (es. 'comande_2026-11-18_pranzo' o 'shop_<idOrdine>'). Vero se
  // questo dispositivo puo' stamparla; falso se l'ha gia' fatta/la sta facendo un altro.
  // La regola Firestore consente di riprenderla solo se fallita o scaduta.
  async function rivendica(chiave) {
    var fb = window._fb;
    try {
      await fb.setDoc(fb.doc(fb.db, 'stampe_auto', chiave), {
        stato: 'in_corso', da: idDispositivo(),
        scadenza: new Date(Date.now() + 5 * 60 * 1000), ts: new Date().toISOString(),
      });
      return true;
    } catch (e) { return false; }
  }

  async function concludi(chiave, ok, err) {
    var fb = window._fb;
    try {
      await fb.setDoc(fb.doc(fb.db, 'stampe_auto', chiave), {
        stato: ok ? 'ok' : 'fallita', da: idDispositivo(),
        scadenza: new Date(Date.now() + 5 * 60 * 1000),
        ts: new Date().toISOString(), err: String(err || '').slice(0, 200),
      });
    } catch (e) { console.error('stampe_auto concludi:', e); }
  }


  // ── Aspetto delle stampe: logo uguale su tutte le stampanti ─────────────────
  // Il logo (logo-scontrini.png) e' convertito in bitmap 1 bit nel formato ePOS
  // <image>: lo stampano uguale l'Epson (diretta) e la Sunmi (il proxy lo converte).
  // tipo: 'conto' | 'riepilogo' | 'report' | 'shop' | 'prova' | 'comanda'
  function logoPer(tipo) {
    var m = autoCfg.aspetto.logo;
    if (m === 'mai') return false;
    if (m === 'tutte') return true;
    return tipo !== 'comanda';
  }

  var logoCache = null;
  function logoXml() {
    if (logoCache !== null) return Promise.resolve(logoCache);
    return new Promise(function (resolve) {
      var img = new Image();
      img.onload = function () {
        try {
          var paperW = 576, logoW = 320;                       // carta 80mm a 203dpi
          var scala = logoW / img.naturalWidth;
          var logoH = Math.round(img.naturalHeight * scala);
          var canvas = document.createElement('canvas');
          canvas.width = paperW; canvas.height = logoH;
          var ctx = canvas.getContext('2d');
          ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, paperW, logoH);
          ctx.drawImage(img, Math.round((paperW - logoW) / 2), 0, logoW, logoH);
          var data = ctx.getImageData(0, 0, paperW, logoH).data;
          var rowBytes = Math.ceil(paperW / 8), mono = new Uint8Array(rowBytes * logoH);
          for (var y = 0; y < logoH; y++) for (var x = 0; x < paperW; x++) {
            var i = (y * paperW + x) * 4;
            if (0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2] < 128) mono[y * rowBytes + (x >> 3)] |= (0x80 >> (x % 8));
          }
          var bin = ''; for (var k = 0; k < mono.length; k++) bin += String.fromCharCode(mono[k]);
          logoCache = '<image width="' + paperW + '" height="' + logoH + '" color="color_1" mode="mono" hri="false">' + btoa(bin) + '</image><feed line="1"/>';
        } catch (e) { logoCache = ''; }
        resolve(logoCache);
      };
      img.onerror = function () { resolve(''); };   // senza logo si stampa comunque (non si memorizza: riprova al prossimo)
      img.src = '/logo-scontrini.png';
    });
  }

  // Logo da mettere in testa al biglietto, oppure '' se per quel tipo e' disattivato.
  async function logoPerStampa(tipo) { return logoPer(tipo) ? await logoXml() : ''; }

  window.GRStampanti = {
    SERVIZI: SERVIZI, TIPI: TIPI, AUTO: AUTO, candidatePer: candidatePer, perAuto: perAuto,
    avvia: avvia, lista: lista, per: per,
    invia: invia, inviaA: inviaA, prova: prova, proxyAttivo: proxyAttivo,
    salva: salva, elimina: elimina,
    avviaAuto: avviaAuto, autoCfg: function () { return autoCfg; }, salvaAuto: salvaAuto,
    rivendica: rivendica, concludi: concludi, idDispositivo: idDispositivo,
    logoPer: logoPer, logoXml: logoXml, logoPerStampa: logoPerStampa,
  };
})();
