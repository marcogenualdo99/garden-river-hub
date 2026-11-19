// Avvisi di reparto nell'app Garden Hub del Sunmi V2, su qualunque pagina della Hub.
// L'ascolto della collezione `notifiche` (copia dei messaggi Telegram, scritta dalla CF telegram-bot)
// stava solo nella home: dentro Shop, Calendario ecc. non arrivava nulla. Questo file lo porta
// in tutte le pagine staff. Fuori dall'app (sito web) non fa niente.
(function () {
  'use strict';
  if (!window.GRNativo || !window.GRNativo.notifica) return;
  var NOMI = { manutenzione: 'Manutenzione', navetta: 'Navetta', pulizie: 'Pulizie', reception: 'Reception', ristorazione: 'Ristorazione', market: 'Market' };
  var visti = null;

  function reparti() {
    try { var v = JSON.parse(localStorage.getItem('gr_notif_reparti') || 'null'); if (Array.isArray(v)) return v; } catch (e) { /* ok */ }
    return Object.keys(NOMI);
  }

  function avvia() {
    var fb = window._fb;
    if (!fb || !fb.onSnapshot || !fb.collection || !fb.db) return;
    try {
      fb.onSnapshot(fb.collection(fb.db, 'notifiche'), function (snap) {
        var primo = visti === null;
        if (primo) visti = {};
        snap.docChanges().forEach(function (ch) {
          if (ch.type !== 'added' || visti[ch.doc.id]) return;
          visti[ch.doc.id] = 1;
          if (primo) return;                       // gli avvisi gia' presenti non si ripetono
          var d = ch.doc.data(), mie = reparti();
          var rep = (d.reparti || []).filter(function (r) { return mie.indexOf(r) >= 0; });
          if (!rep.length) return;
          try { window.GRNativo.notifica((NOMI[rep[0]] || rep[0]) + (d.titolo ? ' · ' + d.titolo : ''), d.testo || ''); } catch (e) { /* ok */ }
        });
      }, function () { /* senza permessi (non loggato): niente */ });
    } catch (e) { /* ok */ }
  }

  if (window._fbReady) avvia();
  else window.addEventListener('firebase-ready', avvia, { once: true });
})();
