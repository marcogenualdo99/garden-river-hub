/* iOS PWA (iPhone con notch): dopo la navigazione indietro / ripristino dalla
   cache env(safe-area-inset-top) a volte vale 0 e la barra in alto finisce
   sotto il notch. Si memorizza l'ultimo valore valido (verticale) e lo si usa
   come minimo tramite --sat-fb, letto da theme.css. */
(function(){
  var root = document.documentElement, probe;
  function leggi(){
    if (!probe) {
      probe = document.createElement('div');
      probe.style.cssText = 'position:fixed;top:0;left:0;width:0;height:0;visibility:hidden;pointer-events:none;padding-top:env(safe-area-inset-top)';
      (document.body || root).appendChild(probe);
    }
    return parseFloat(getComputedStyle(probe).paddingTop) || 0;
  }
  function applica(){
    try {
      var portrait = window.innerHeight > window.innerWidth;
      var v = leggi(), salvato = 0;
      try { salvato = parseFloat(localStorage.getItem('gr_sat')) || 0; } catch(e){}
      if (v > 0) { if (portrait && v !== salvato) { try { localStorage.setItem('gr_sat', String(v)); } catch(e){} } salvato = portrait ? v : salvato; }
      root.style.setProperty('--sat-fb', (portrait && salvato > 0 ? salvato : 0) + 'px');
    } catch(e){}
  }
  applica();
  document.addEventListener('DOMContentLoaded', applica);
  window.addEventListener('pageshow', function(){ applica(); setTimeout(applica, 100); setTimeout(applica, 500); });
  window.addEventListener('resize', applica);
  window.addEventListener('orientationchange', function(){ setTimeout(applica, 300); });
})();
