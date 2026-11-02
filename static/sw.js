/* ==================================================================
   sw.js — LE SERVICE WORKER DES RAPPELS (v7.12.0)
   Les Équipes du Rosaire — Diocèse de Grand-Bassam.
   Il vit silencieux dans le téléphone : quand une ronde de la chaîne
   (06h00 · 12h00 · 18h00 · 21h00) frappe, il montre la notification
   « 📿 Ta dizaine du jour t'attend » — même si l'application est
   fermée. Un tap sur la notification ouvre l'Espace de Prière.
   v7.12.2 — LE PASSEUR : il écoute aussi chaque demande (fetch) et la
   laisse passer telle quelle vers le réseau. L'application reste
   exactement la même — mais le téléphone qui regarde la page
   d'installation la déclare désormais « vraie application poseable » :
   le menu ⋮ propose « Installer l'application » et le raccourci posé
   porte le bon visage, ouvre plein écran et se souvient du fidèle.
   ================================================================== */
const ICONES = '/app/static/icon_espace_192.png';

self.addEventListener('install', (e) => { self.skipWaiting(); });

self.addEventListener('activate', (e) => { e.waitUntil(self.clients.claim()); });

// v7.12.2 — LE PASSEUR : chaque demande file droit au réseau, rien n'est
// retenu, rien n'est modifié (pas de respondWith). Il rend la page
// d'installation « installable » aux yeux du téléphone — c'est tout.
self.addEventListener('fetch', () => { });

self.addEventListener('push', (e) => {
  let d = {};
  try { d = e.data.json(); } catch (_) {
    d = { titre: '📿 Les Équipes du Rosaire',
          corps: 'Ta dizaine du jour t\u2019attend.',
          lien: '/?espace=1' };
  }
  e.waitUntil(self.registration.showNotification(
    d.titre || '📿 Les Équipes du Rosaire', {
      body: d.corps || 'Ta dizaine du jour t\u2019attend.',
      icon: ICONES, badge: ICONES, tag: 'dizaine-du-jour',
      renotify: true, vibrate: [200, 100, 200],
      data: { lien: d.lien || '/?espace=1' }
    }));
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const cible = (e.notification.data && e.notification.data.lien) || '/?espace=1';
  e.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true })
    .then((liste) => {
      for (const fen of liste) {
        if ('focus' in fen) {
          try { fen.navigate(cible); } catch (_) { }
          return fen.focus();
        }
      }
      return clients.openWindow(cible);
    }));
});
