// Sessione operatore condivisa da tutti i moduli della suite.
//
// Dopo il PIN, la Hub (index.html) fa signInWithCustomToken con il token
// rilasciato dalla Cloud Function 'auth-operatori'. Quel token porta il claim
// `operatore`, che le regole Firestore/Storage richiedono: senza, nessun dato.
// I moduli NON fanno più login anonimo: usano la sessione già aperta dalla Hub.
//
//  • App Firebase di default: la sessione è già persistita (stessa origine) →
//    basta attendere che venga ripristinata.
//  • App con nome (es. "ristorazione"): hanno una sessione propria; se manca,
//    se ne chiede una nuova alla funzione ('rinnova') usando quella della Hub.
import { initializeApp, getApps } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getAuth, signInWithCustomToken } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";

export const AUTH_FN_URL = 'https://auth-operatori-113994721180.europe-west1.run.app';

const CFG = {
  apiKey: "AIzaSyBAnVI0MTNKZ9rIHpATgKyCp88nq0u0vsY",
  authDomain: "garden-river-conti-febed.firebaseapp.com",
  projectId: "garden-river-conti-febed",
  storageBucket: "garden-river-conti-febed.firebasestorage.app",
  messagingSenderId: "113994721180",
  appId: "1:113994721180:web:c41d309c9270134b640a59"
};

function operatoreAutenticato(auth) {
  const u = auth.currentUser;
  return u && !u.isAnonymous ? u : null;
}

export async function sessioneHub(auth) {
  await auth.authStateReady();
  const gia = operatoreAutenticato(auth);
  if (gia) return gia;

  // App con nome senza sessione: prendila dall'app di default (quella della Hub).
  const baseApp = getApps().find(a => a.name === '[DEFAULT]') || initializeApp(CFG);
  const base = getAuth(baseApp);
  await base.authStateReady();
  const u = operatoreAutenticato(base);
  if (!u) throw new Error('sessione-hub-assente');
  if (base === auth) throw new Error('sessione-hub-assente');

  const res = await fetch(AUTH_FN_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ azione: 'rinnova', id_token: await u.getIdToken() }),
  });
  const j = await res.json().catch(() => ({}));
  if (!j.ok || !j.token) throw new Error('rinnovo-sessione-fallito');
  return (await signInWithCustomToken(auth, j.token)).user;
}
