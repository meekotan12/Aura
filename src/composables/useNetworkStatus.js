/**
 * Reactive Network Status Composable
 *
 * Uses @capacitor/network on native, falls back to navigator.onLine on web.
 */
import { ref, onMounted, onBeforeUnmount, readonly } from 'vue'
import { Capacitor } from '@capacitor/core'

const isOnline = ref(true)
const connectionType = ref('unknown')
let networkListenerHandle = null
let initialized = false

async function initNetworkListener() {
    if (initialized) return
    initialized = true

    if (Capacitor.isNativePlatform()) {
        try {
            const { Network } = await import('@capacitor/network')
            const status = await Network.getStatus()
            isOnline.value = status.connected
            connectionType.value = status.connectionType || 'unknown'

            networkListenerHandle = await Network.addListener('networkStatusChange', (status) => {
                isOnline.value = status.connected
                connectionType.value = status.connectionType || 'unknown'
            })
        } catch {
            // fallback to web
            isOnline.value = navigator.onLine
            setupWebListeners()
        }
    } else {
        isOnline.value = navigator.onLine
        connectionType.value = navigator.connection?.effectiveType || 'unknown'
        setupWebListeners()
    }
}

function setupWebListeners() {
    if (typeof window === 'undefined') return

    window.addEventListener('online', () => {
        isOnline.value = true
    })

    window.addEventListener('offline', () => {
        isOnline.value = false
    })
}

// Auto-initialize
if (typeof window !== 'undefined') {
    initNetworkListener()
}

export function useNetworkStatus() {
    return {
        isOnline: readonly(isOnline),
        isOffline: ref(false), // computed below
        connectionType: readonly(connectionType),
    }
}

// Also export raw refs for non-composable usage
export { isOnline, connectionType }
