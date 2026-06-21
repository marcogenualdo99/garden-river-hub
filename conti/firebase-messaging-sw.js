importScripts('https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.12.2/firebase-messaging-compat.js');

firebase.initializeApp({
  apiKey: "AIzaSyBAnVI0MTNKZ9rIHpATgKyCp88nq0u0vsY",
  authDomain: "garden-river-conti-febed.firebaseapp.com",
  projectId: "garden-river-conti-febed",
  storageBucket: "garden-river-conti-febed.firebasestorage.app",
  messagingSenderId: "113994721180",
  appId: "1:113994721180:web:c41d309c9270134b640a59"
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {
  const { title, body } = payload.notification;
  self.registration.showNotification(title, {
    body,
    icon: '/logo-hub-app.jpg',
    badge: '/logo-hub-app.jpg',
    tag: 'checkout-reminder',
    requireInteraction: true
  });
});
