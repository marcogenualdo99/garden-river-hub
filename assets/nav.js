/* Navigazione condivisa per i moduli che non hanno ancora la propria copia:
   apertura/chiusura categorie, drawer mobile, uscita, icone e animazione a
   cascata del menu. Le funzioni si definiscono solo se la pagina non ha già
   la propria versione. */
(function () {
  if (typeof window.toggleNavGroup === 'undefined') {
    window.toggleNavGroup = function (btn) {
      btn.classList.toggle('collapsed');
      btn.nextElementSibling.classList.toggle('collapsed');
    };
  }
  if (typeof window.toggleDrawer === 'undefined') {
    window.toggleDrawer = function (open) {
      document.getElementById('drawer').classList.toggle('open', open);
      document.getElementById('drawer-overlay').classList.toggle('open', open);
      document.body.classList.toggle('drawer-open', open);
    };
  }
  if (typeof window.hydrateIcons === 'function') window.hydrateIcons();
  document.querySelectorAll('.drawer, .sidebar').forEach(function (menu) {
    menu.querySelectorAll('.sidebar-brand > *, .nav-group-header, .nav-item').forEach(function (el, i) {
      el.style.setProperty('--i', i);
    });
  });
})();
