import { computed, ref } from 'vue'

const deferredInstallPrompt = ref(null)
const installErrorMessage = ref('')
const installPromptAvailable = ref(false)
const installed = ref(false)

let initialized = false

function isBrowser() {
    return typeof window !== 'undefined' && typeof navigator !== 'undefined'
}

function isStandaloneDisplay() {
    if (!isBrowser()) return false

    return (
        window.matchMedia?.('(display-mode: standalone)').matches ||
        window.matchMedia?.('(display-mode: fullscreen)').matches ||
        window.navigator?.standalone === true
    )
}

function isIosDevice() {
    if (!isBrowser()) return false

    const userAgent = window.navigator.userAgent || ''
    return /iphone|ipad|ipod/i.test(userAgent)
}

function isSafariBrowser() {
    if (!isBrowser()) return false

    const userAgent = window.navigator.userAgent || ''
    const vendor = window.navigator.vendor || ''
    const isAppleVendor = /apple/i.test(vendor)
    const isCriOS = /crios/i.test(userAgent)
    const isFxiOS = /fxios/i.test(userAgent)
    const isEdgeiOS = /edgios/i.test(userAgent)

    return isAppleVendor && !isCriOS && !isFxiOS && !isEdgeiOS
}

function syncInstalledState() {
    installed.value = isStandaloneDisplay()

    if (installed.value) {
        deferredInstallPrompt.value = null
        installPromptAvailable.value = false
        installErrorMessage.value = ''
    }
}

export const isPwaInstalled = computed(() => installed.value)

export const canPromptPwaInstall = computed(() => {
    return installPromptAvailable.value && !installed.value
})

export const hasManualPwaInstallInstructions = computed(() => {
    if (!isBrowser() || installed.value || installPromptAvailable.value) return false
    return isIosDevice()
})

export const pwaInstallHelpText = computed(() => {
    if (installed.value) {
        return 'Aura is already installed on this device.'
    }

    if (canPromptPwaInstall.value) {
        return 'Install Aura for a faster home screen experience and standalone launch.'
    }

    if (hasManualPwaInstallInstructions.value) {
        return isSafariBrowser()
            ? 'On iPhone or iPad, open the Share menu in Safari and choose Add to Home Screen.'
            : 'Open this page in Safari to install Aura on iPhone or iPad.'
    }

    return 'Install becomes available when the browser confirms this app is ready for home screen install.'
})

export const pwaInstallButtonLabel = computed(() => {
    if (installed.value) return 'Installed'
    if (canPromptPwaInstall.value) return 'Install Aura'
    if (hasManualPwaInstallInstructions.value) {
        return isSafariBrowser() ? 'Add to Home Screen' : 'Open in Safari'
    }
    return 'PWA Ready'
})

export function startPwaInstallSync() {
    if (initialized || !isBrowser()) return
    initialized = true

    syncInstalledState()

    const standaloneMediaQuery = window.matchMedia?.('(display-mode: standalone)')
    const handleDisplayModeChange = () => syncInstalledState()
    const handleBeforeInstallPrompt = (event) => {
        event.preventDefault()
        deferredInstallPrompt.value = event
        installPromptAvailable.value = !installed.value
        installErrorMessage.value = ''
    }
    const handleAppInstalled = () => {
        syncInstalledState()
    }

    standaloneMediaQuery?.addEventListener?.('change', handleDisplayModeChange)
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    window.addEventListener('appinstalled', handleAppInstalled)
}

export async function installPwaApp() {
    syncInstalledState()

    if (installed.value) {
        return { status: 'already_installed' }
    }

    const promptEvent = deferredInstallPrompt.value
    if (!promptEvent) {
        return { status: 'unavailable' }
    }

    installErrorMessage.value = ''
    deferredInstallPrompt.value = null
    installPromptAvailable.value = false

    try {
        await promptEvent.prompt()
        const choice = await promptEvent.userChoice
        syncInstalledState()

        return {
            status: choice?.outcome === 'accepted' ? 'accepted' : 'dismissed',
        }
    } catch (error) {
        installErrorMessage.value =
            error instanceof Error
                ? error.message
                : 'The install prompt could not be opened on this device.'

        return { status: 'error' }
    }
}

export function clearPwaInstallError() {
    installErrorMessage.value = ''
}

export const pwaInstallError = computed(() => installErrorMessage.value)
