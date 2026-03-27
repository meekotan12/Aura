const CACHE_NAME = 'aura-shell-v4'
const APP_SHELL_URL = '/'
const SHELL_ASSETS = [
  '/',
  '/manifest.webmanifest',
  '/runtime-config.js',
  '/logos/aura.png',
  '/pwa-192.png',
  '/pwa-512.png',
  '/pwa-maskable-512.png',
]
const LOCALHOST_HOSTNAMES = new Set(['localhost', '127.0.0.1', '[::1]'])
const STATIC_ASSET_PATTERN = /\.(?:png|jpg|jpeg|svg|webp|woff|woff2|ttf)$/i
const CODE_ASSET_PATTERN = /\.(?:js|css)$/i

function isLocalhostHost(hostname) {
  return LOCALHOST_HOSTNAMES.has(hostname) || hostname.endsWith('.local')
}

function isCacheableStaticAsset(pathname) {
  return STATIC_ASSET_PATTERN.test(pathname)
}

function isCodeAsset(pathname) {
  return CODE_ASSET_PATTERN.test(pathname)
}

const isLocalhost = isLocalhostHost(self.location.hostname)

async function deleteOldAuraCaches() {
  const keys = await caches.keys()
  await Promise.all(
    keys
      .filter((key) => key.startsWith('aura-') && key !== CACHE_NAME)
      .map((key) => caches.delete(key))
  )
}

async function cacheResponse(request, response) {
  if (!response || !response.ok) return response

  const cache = await caches.open(CACHE_NAME)
  await cache.put(request, response.clone())
  return response
}

async function resolveNavigationResponse(event) {
  try {
    const preloadResponse = await event.preloadResponse
    if (preloadResponse) {
      void cacheResponse(event.request, preloadResponse)
      return preloadResponse
    }

    const networkResponse = await fetch(event.request)
    void cacheResponse(event.request, networkResponse)
    return networkResponse
  } catch {
    const cachedResponse = await caches.match(event.request)
    if (cachedResponse) return cachedResponse

    return (
      await caches.match(APP_SHELL_URL)
      || Response.error()
    )
  }
}

async function resolveCodeAssetResponse(request) {
  try {
    const networkResponse = await fetch(request)
    return await cacheResponse(request, networkResponse)
  } catch {
    return (
      await caches.match(request)
      || Response.error()
    )
  }
}

async function resolveStaticAssetResponse(request) {
  const cachedResponse = await caches.match(request)
  if (cachedResponse) return cachedResponse

  try {
    const networkResponse = await fetch(request)
    if (networkResponse.ok) {
      void cacheResponse(request, networkResponse)
    }
    return networkResponse
  } catch {
    return Response.error()
  }
}

if (isLocalhost) {
  self.addEventListener('install', () => {
    self.skipWaiting()
  })

  self.addEventListener('activate', (event) => {
    event.waitUntil(
      caches.keys()
        .then((keys) => Promise.all(keys.filter((key) => key.startsWith('aura-')).map((key) => caches.delete(key))))
        .then(() => self.registration.unregister())
        .then(() => self.clients.matchAll({ type: 'window' }))
        .then((clients) => Promise.all(clients.map((client) => client.navigate(client.url))))
    )
  })
} else {
  self.addEventListener('install', (event) => {
    event.waitUntil(
      caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS))
    )
    self.skipWaiting()
  })

  self.addEventListener('activate', (event) => {
    event.waitUntil((async () => {
      await deleteOldAuraCaches()

      if ('navigationPreload' in self.registration) {
        await self.registration.navigationPreload.enable().catch(() => null)
      }

      await self.clients.claim()
    })())
  })

  self.addEventListener('fetch', (event) => {
    if (event.request.method !== 'GET') return

    const requestUrl = new URL(event.request.url)

    if (requestUrl.origin !== self.location.origin) return
    if (requestUrl.pathname.startsWith('/__backend__') || requestUrl.pathname.startsWith('/api/')) return

    if (event.request.mode === 'navigate') {
      event.respondWith(resolveNavigationResponse(event))
      return
    }

    if (isCodeAsset(requestUrl.pathname)) {
      event.respondWith(resolveCodeAssetResponse(event.request))
      return
    }

    if (isCacheableStaticAsset(requestUrl.pathname) || requestUrl.pathname === '/runtime-config.js') {
      event.respondWith(resolveStaticAssetResponse(event.request))
    }
  })
}
