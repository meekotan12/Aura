import { computed, ref } from 'vue'
import { Capacitor } from '@capacitor/core'

const MOBILE_FULLSCREEN_HINT_KEY = 'aura_mobile_fullscreen_hint_seen'
const mobileFullscreenEligible = ref(false)
const mobileFullscreenHintDismissed = ref(false)

function isAndroid() {
    if (typeof navigator === 'undefined') return false
    return /android/i.test(navigator.userAgent || '')
}

function isLikelyMobileViewport() {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false
    return window.matchMedia('(max-width: 900px)').matches
}

function isStandaloneDisplay() {
    if (typeof window === 'undefined') return false

    return (
        window.matchMedia?.('(display-mode: standalone)').matches ||
        window.matchMedia?.('(display-mode: fullscreen)').matches ||
        window.navigator?.standalone === true
    )
}

function canRequestFullscreen() {
    if (typeof document === 'undefined') return false
    return (
        typeof document.documentElement?.requestFullscreen === 'function' &&
        document.fullscreenEnabled !== false
    )
}

function markMobileFullscreenHintDismissed() {
    mobileFullscreenHintDismissed.value = true

    if (typeof window !== 'undefined') {
        window.sessionStorage?.setItem(MOBILE_FULLSCREEN_HINT_KEY, '1')
    }
}

export const mobileFullscreenHintVisible = computed(() => {
    return mobileFullscreenEligible.value && !mobileFullscreenHintDismissed.value
})

export async function requestMobileFullscreen() {
    if (!canRequestFullscreen() || isStandaloneDisplay()) return

    try {
        await document.documentElement.requestFullscreen({ navigationUI: 'hide' })
    } catch {
        // Ignore platform-level fullscreen rejections. Android browsers may refuse
        // this outside supported contexts, but the app still benefits from PWA mode.
    }
}

export function startMobileFullscreenSync() {
    if (typeof window === 'undefined') return
    // In native Capacitor app, already fullscreen — no hint needed
    if (Capacitor.isNativePlatform()) return

    const eligible =
        isAndroid() &&
        isLikelyMobileViewport() &&
        !isStandaloneDisplay() &&
        canRequestFullscreen()

    mobileFullscreenEligible.value = eligible
    mobileFullscreenHintDismissed.value =
        window.sessionStorage?.getItem(MOBILE_FULLSCREEN_HINT_KEY) === '1'

    if (!eligible) return

    let attempted = false

    const handleFirstInteraction = () => {
        if (attempted) return
        attempted = true
        markMobileFullscreenHintDismissed()
        requestMobileFullscreen().catch(() => null)
    }

    const handleFullscreenChange = () => {
        if (document.fullscreenElement) {
            markMobileFullscreenHintDismissed()
        }
    }

    window.addEventListener('pointerup', handleFirstInteraction, {
        once: true,
        passive: true,
    })
    document.addEventListener('fullscreenchange', handleFullscreenChange, {
        passive: true,
    })
}

async function unregisterAuraServiceWorkers() {
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) return

    try {
        const registrations = await navigator.serviceWorker.getRegistrations()
        await Promise.all(registrations.map((registration) => registration.unregister().catch(() => false)))
    } catch {
        // Ignore service worker cleanup failures on unsupported browsers.
    }

    if (typeof caches === 'undefined') return

    try {
        const cacheKeys = await caches.keys()
        await Promise.all(
            cacheKeys
                .filter((key) => key.startsWith('aura-'))
                .map((key) => caches.delete(key))
        )
    } catch {
        // Ignore cache cleanup failures; they should never block boot.
    }
}

export function registerAuraServiceWorker() {
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) return
    // Skip SW registration in native Capacitor app
    if (Capacitor.isNativePlatform()) return
    const hostname = String(window.location.hostname || '').toLowerCase()
    const isLocalhost =
        hostname === 'localhost' ||
        hostname === '127.0.0.1' ||
        hostname === '[::1]' ||
        hostname.endsWith('.local')

    if (!import.meta.env.PROD || isLocalhost) {
        window.addEventListener('load', () => {
            unregisterAuraServiceWorkers().catch(() => null)
        }, { once: true })
        return
    }

    if (!window.isSecureContext) return

    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' }).catch(() => null)
    }, { once: true })
}
