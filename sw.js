// =========================================================================
// SERVICE WORKER - PRO-ELÉTRICA CAD NBR 5410 (PWA OFFLINE / CACHE)
// =========================================================================
const CACHE_NAME = 'pro-eletrica-cad-v1.3';
const STATIC_ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './libs/three.min.js',
  './libs/OrbitControls.js',
  './icon.svg',
  './icon-192.png',
  './icon-512.png',
  './apple-touch-icon.png'
];

// Instalação: Pré-armazena em cache os arquivos essenciais locais
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[PWA SW] Pre-caching offline app shell');
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('[PWA SW] Falha ao pré-carregar alguns assets:', err);
      });
    })
  );
  self.skipWaiting();
});

// Ativação: Limpa versões antigas do cache
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            console.log('[PWA SW] Removendo cache legado:', key);
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Interceptação de Requisições: Stale-While-Revalidate para máxima agilidade e suporte offline
self.addEventListener('fetch', (event) => {
  // Apenas métodos GET
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      const fetchPromise = fetch(event.request)
        .then((networkResponse) => {
          // Se a resposta for válida, armazena no cache para uso offline posterior
          if (networkResponse && networkResponse.status === 200) {
            const responseToCache = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => {
              // Não armazena chrome-extension ou esquemas desconhecidos
              if (event.request.url.startsWith('http')) {
                cache.put(event.request, responseToCache);
              }
            });
          }
          return networkResponse;
        })
        .catch(() => {
          // Se estiver sem internet, retorna o que estiver em cache
          return cachedResponse;
        });

      // Retorna o cache se disponível para carregamento instantâneo, ou aguarda a rede
      return cachedResponse || fetchPromise;
    })
  );
});
