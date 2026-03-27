import { Capacitor } from '@capacitor/core'

const DEFAULT_WEB_API_BASE_URL = '/__backend__'
const DEFAULT_API_TIMEOUT_MS = 15000
const DEFAULT_NATIVE_API_BASE_URL = 'https://backend-api-production-32e5.up.railway.app'

function getRuntimeConfig() {
  if (typeof window === 'undefined') return {}

  const runtimeConfig = window.__AURA_RUNTIME_CONFIG__
  return runtimeConfig && typeof runtimeConfig === 'object' ? runtimeConfig : {}
}

function readFirstDefinedString(values = []) {
  for (const value of values) {
    const normalized = String(value ?? '').trim()
    if (normalized) return normalized
  }

  return ''
}

function readFirstAbsoluteHttpUrl(values = []) {
  for (const value of values) {
    const normalized = String(value ?? '').trim()
    if (/^https?:\/\//i.test(normalized)) return normalized
  }

  return ''
}

function normalizeApiBaseUrl(value = '') {
  const normalized = String(value || '').trim().replace(/\/+$/, '')
  if (!normalized) return DEFAULT_WEB_API_BASE_URL

  try {
    const url = new URL(normalized)
    if (url.pathname === '/api') {
      url.pathname = ''
    }
    return url.toString().replace(/\/+$/, '')
  } catch {
    if (normalized === '/api') return ''
    if (normalized.endsWith('/api')) {
      return normalized.replace(/\/api$/, '')
    }
    return normalized
  }
}

function getBrowserOrigin() {
  if (typeof window !== 'undefined' && window.location?.origin) {
    return window.location.origin
  }

  return 'http://localhost:5173'
}

function resolveNativeApiBaseUrl(baseUrl = '') {
  const runtimeConfig = getRuntimeConfig()
  const nativeUrl = readFirstAbsoluteHttpUrl([
    baseUrl,
    runtimeConfig.nativeApiBaseUrl,
    runtimeConfig.apiBaseUrl,
    runtimeConfig.backendBaseUrl,
    runtimeConfig.backendOrigin,
    import.meta.env.VITE_NATIVE_API_BASE_URL,
    import.meta.env.VITE_BACKEND_PROXY_TARGET,
    import.meta.env.VITE_API_BASE_URL,
  ])

  return normalizeApiBaseUrl(nativeUrl || DEFAULT_NATIVE_API_BASE_URL)
}

export function resolveApiBaseUrl(baseUrl = '') {
  if (Capacitor.isNativePlatform()) {
    return resolveNativeApiBaseUrl(baseUrl)
  }

  const runtimeConfig = getRuntimeConfig()
  return normalizeApiBaseUrl(readFirstDefinedString([
    baseUrl,
    runtimeConfig.apiBaseUrl,
    runtimeConfig.backendBaseUrl,
    runtimeConfig.backendOrigin,
    import.meta.env.VITE_API_BASE_URL,
  ]))
}

export function resolveAbsoluteApiBaseUrl(baseUrl = '') {
  const resolved = resolveApiBaseUrl(baseUrl)

  if (!resolved) {
    return getBrowserOrigin()
  }

  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(resolved)) {
    return resolved
  }

  if (resolved.startsWith('/')) {
    return `${getBrowserOrigin()}${resolved}`
  }

  return resolved
}

export function isNgrokApiBaseUrl(baseUrl = '') {
  try {
    const hostname = new URL(resolveAbsoluteApiBaseUrl(baseUrl)).hostname.toLowerCase()
    return /(?:^|\.)ngrok(?:-free)?\.(?:app|dev|io)$/.test(hostname)
  } catch {
    return false
  }
}

export function resolveApiTimeoutMs(value = null) {
  const runtimeConfig = getRuntimeConfig()
  const candidates = [
    value,
    runtimeConfig.apiTimeoutMs,
    import.meta.env.VITE_API_TIMEOUT_MS,
  ]

  for (const candidate of candidates) {
    const normalized = Number(candidate)
    if (Number.isFinite(normalized) && normalized > 0) {
      return normalized
    }
  }

  return DEFAULT_API_TIMEOUT_MS
}
