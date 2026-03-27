/**
 * Native Features Composable
 *
 * Provides haptic feedback, status bar control, screen wake lock,
 * and app lifecycle hooks using Capacitor plugins.
 */
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { Capacitor } from '@capacitor/core'

const isNative = Capacitor.isNativePlatform()

let HapticsPlugin = null
let StatusBarPlugin = null
let AppPlugin = null

async function loadHaptics() {
    if (HapticsPlugin) return HapticsPlugin
    try {
        const mod = await import('@capacitor/haptics')
        HapticsPlugin = mod.Haptics
        return HapticsPlugin
    } catch {
        return null
    }
}

async function loadStatusBar() {
    if (StatusBarPlugin) return StatusBarPlugin
    try {
        const mod = await import('@capacitor/status-bar')
        StatusBarPlugin = mod.StatusBar
        return StatusBarPlugin
    } catch {
        return null
    }
}

async function loadApp() {
    if (AppPlugin) return AppPlugin
    try {
        const mod = await import('@capacitor/app')
        AppPlugin = mod.App
        return AppPlugin
    } catch {
        return null
    }
}

/**
 * Light haptic feedback (for button taps, selection changes)
 */
export async function vibrateLight() {
    if (!isNative) return
    try {
        const Haptics = await loadHaptics()
        if (Haptics) {
            await Haptics.impact({ style: 'light' })
        }
    } catch {
        // silently fail
    }
}

/**
 * Medium haptic feedback (for confirmations, toggles)
 */
export async function vibrateMedium() {
    if (!isNative) return
    try {
        const Haptics = await loadHaptics()
        if (Haptics) {
            await Haptics.impact({ style: 'medium' })
        }
    } catch {
        // silently fail
    }
}

/**
 * Error/warning haptic notification
 */
export async function vibrateError() {
    if (!isNative) return
    try {
        const Haptics = await loadHaptics()
        if (Haptics) {
            await Haptics.notification({ type: 'error' })
        }
    } catch {
        // silently fail
    }
}

/**
 * Set status bar color (native only)
 */
export async function setStatusBarColor(hexColor) {
    if (!isNative) return
    try {
        const StatusBar = await loadStatusBar()
        if (StatusBar) {
            await StatusBar.setBackgroundColor({ color: hexColor })
        }
    } catch {
        // silently fail
    }
}

/**
 * Hide status bar for immersive views (e.g., face scan)
 */
export async function hideStatusBar() {
    if (!isNative) return
    try {
        const StatusBar = await loadStatusBar()
        if (StatusBar) {
            await StatusBar.hide()
        }
    } catch {
        // silently fail
    }
}

/**
 * Show status bar
 */
export async function showStatusBar() {
    if (!isNative) return
    try {
        const StatusBar = await loadStatusBar()
        if (StatusBar) {
            await StatusBar.show()
        }
    } catch {
        // silently fail
    }
}

/**
 * Register a handler for the Android hardware back button.
 * Returns a cleanup function to remove the listener.
 */
export function onBackButton(handler) {
    if (!isNative) return () => {}

    let listenerHandle = null

    loadApp().then((App) => {
        if (!App) return
        App.addListener('backButton', handler).then((handle) => {
            listenerHandle = handle
        })
    })

    return () => {
        if (listenerHandle?.remove) {
            listenerHandle.remove()
        }
    }
}

/**
 * Register a handler for app state changes (foreground/background).
 */
export function onAppStateChange(handler) {
    if (!isNative) return () => {}

    let listenerHandle = null

    loadApp().then((App) => {
        if (!App) return
        App.addListener('appStateChange', handler).then((handle) => {
            listenerHandle = handle
        })
    })

    return () => {
        if (listenerHandle?.remove) {
            listenerHandle.remove()
        }
    }
}

/**
 * Request screen wake lock to prevent screen sleep (e.g., during face scan)
 */
export async function requestWakeLock() {
    if (typeof navigator === 'undefined' || !navigator.wakeLock) return null

    try {
        return await navigator.wakeLock.request('screen')
    } catch {
        return null
    }
}

/**
 * Composable version with lifecycle management
 */
export function useNativeFeatures() {
    const isNativePlatform = ref(isNative)

    return {
        isNative: isNativePlatform,
        vibrateLight,
        vibrateMedium,
        vibrateError,
        setStatusBarColor,
        hideStatusBar,
        showStatusBar,
        onBackButton,
        onAppStateChange,
        requestWakeLock,
    }
}
