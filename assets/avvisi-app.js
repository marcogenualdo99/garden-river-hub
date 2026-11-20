// Avvisi di reparto nell'app Garden Hub del Sunmi V2, su qualunque pagina della Hub.
// L'ascolto della collezione `notifiche` (copia dei messaggi Telegram, scritta dalla CF telegram-bot)
// stava solo nella home: dentro Shop, Calendario ecc. non arrivava nulla. Questo file lo porta
// in tutte le pagine staff. Fuori dall'app (sito web) non fa niente.
(function () {
  'use strict';
  if (!window.GRNativo || !window.GRNativo.notifica) return;
  var NOMI = { manutenzione: 'Manutenzione', navetta: 'Navetta', pulizie: 'Pulizie', reception: 'Reception', ristorazione: 'Ristorazione', market: 'Market' };
  var visti = null;
  function log(m) { try { console.log('[avvisi] ' + m); } catch (e) { /* ok */ } }

  function reparti() {
    try { var v = JSON.parse(localStorage.getItem('gr_notif_reparti') || 'null'); if (Array.isArray(v)) return v; } catch (e) { /* ok */ }
    return Object.keys(NOMI);
  }

  // Con app chiusa gli avvisi li gestisce il servizio nativo dell'app (feed dalla CF telegram-bot).
  // Qui gli si passano i reparti scelti e, la prima volta, la chiave del feed (la dà la CF a un operatore loggato).
  var BOT = 'https://telegram-bot-113994721180.europe-west1.run.app';
  var tentativi = 0;
  function riprova() { if (++tentativi < 40) setTimeout(provisiona, 4000); }   // l'operatore può non aver ancora fatto il login: si riprova per ~3 minuti
  function provisiona() {
    var N = window.GRNativo;
    try { if (N.impostaReparti) N.impostaReparti(JSON.stringify(reparti())); } catch (e) { /* ok */ }
    try {
      if (!N.impostaFeed || (N.feedPronto && N.feedPronto())) return;
      if (typeof window.fetchStaff !== 'function') { log('fetchStaff non ancora disponibile, riprovo'); riprova(); return; }
      window.fetchStaff(BOT, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ evento: 'feed_chiave' }) })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d && d.ok && d.key) { N.impostaFeed(BOT, d.key); log('feed avvisi configurato'); }
          else { log('feed non configurato: ' + (d && d.errore)); riprova(); }
        })
        .catch(function () { riprova(); });
    } catch (e) { /* ok */ }
  }

  function avvia() {
    setTimeout(provisiona, 1500);
    if (typeof window.mostraAvvisoApp === 'function') return;   // la home della Hub ha già il suo ascolto
    var fb = window._fb;
    if (!fb || !fb.onSnapshot || !fb.collection || !fb.db) { log('Firebase non disponibile su questa pagina'); return; }
    log('ascolto notifiche avviato, reparti: ' + reparti().join(','));
    try {
      fb.onSnapshot(fb.collection(fb.db, 'notifiche'), function (snap) {
        var primo = visti === null;
        log('snapshot: ' + snap.size + ' doc, primo=' + primo);
        if (primo) visti = {};
        snap.docChanges().forEach(function (ch) {
          if (ch.type !== 'added' || visti[ch.doc.id]) return;
          visti[ch.doc.id] = 1;
          if (!primo) log('nuovo avviso ' + JSON.stringify(ch.doc.data().reparti));
          if (primo) return;                       // gli avvisi gia' presenti non si ripetono
          var d = ch.doc.data(), mie = reparti();
          var rep = (d.reparti || []).filter(function (r) { return mie.indexOf(r) >= 0; });
          if (!rep.length) return;
          try { window.GRNativo.notifica((NOMI[rep[0]] || rep[0]) + (d.titolo ? ' · ' + d.titolo : ''), d.testo || ''); } catch (e) { /* ok */ }
        });
      }, function (e) { log('errore ascolto: ' + (e && e.code)); });
    } catch (e) { /* ok */ }
  }

  if (window._fbReady) avvia();
  else window.addEventListener('firebase-ready', avvia, { once: true });
})();
