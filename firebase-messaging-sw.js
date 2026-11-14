// Le notifiche push sono state sostituite da Telegram. Questo service worker resta
// solo per rimuovere se stesso dai dispositivi che lo avevano registrato.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => {
  e.waitUntil(self.registration.unregister());
});
