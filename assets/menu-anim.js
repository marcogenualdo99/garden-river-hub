/* Indice progressivo per l'ingresso a cascata delle voci del menu laterale
   (vedi assets/restyle.css). Da includere a fine pagina nei moduli. */
(function () {
  document.querySelectorAll('.drawer, .sidebar').forEach(function (menu) {
    menu.querySelectorAll('.sidebar-brand > *, .nav-group-header, .nav-item').forEach(function (el, i) {
      el.style.setProperty('--i', i);
    });
  });
})();
