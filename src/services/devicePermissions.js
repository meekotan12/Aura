/**
 * Centralized Device Permission Service
 *
 * Uses Capacitor native plugins when running in a native app,
 * falls back to web APIs when running in the browser.
 */
import { Capacitor } from '@capacitor/core'

let CameraPlugin = null
let GeolocationPlugin = null
let lastResolvedPosition = null
const LOCATION_SERVICES_DISABLED_CODE = 'OS-PLUG-GLOC-0007'
const LOCATION_PERMISSION_DENIED_CODE = 'OS-PLUG-GLOC-0003'
const LOCATION_SETTINGS_DENIED_CODE = 'OS-PLUG-GLOC-0009'
const LOCATION_TIMEOUT_CODE = 'OS-PLUG-GLOC-0010'
const LOCATION_SETTINGS_ERROR_CODE = 'OS-PLUG-GLOC-0016'
const LOCATION_NETWORK_OFF_CODE = 'OS-PLUG-GLOC-0017'
const WEB_GEOLOCATION_PERMISSION_DENIED_CODE = 1
const WEB_GEOLOCATION_POSITION_UNAVAILABLE_CODE = 2
const WEB_GEOLOCATION_TIMEOUT_CODE = 3
const DEFAULT_NATIVE_LOCATION_OPTIONS = {
    enableHighAccuracy: true,
    timeout: 20000,
    maximumAge: 10000,
    enableLocationFallback: true,
}
const DEFAULT_WEB_LOCATION_OPTIONS = {
    enableHighAccuracy: true,
    timeout: 15000,
    maximumAge: 10000,
}
const DEFAULT_LOCATION_CACHE_MAX_AGE_MS = 60000
const DEFAULT_LOCATION_PRIME_OPTIONS = {
    enableHighAccuracy: false,
    timeout: 7000,
    maximumAge: DEFAULT_LOCATION_CACHE_MAX_AGE_MS,
}
const DEFAULT_PRECISE_LOCATION_TIMEOUT_MS = 18000
const DEFAULT_PRECISE_LOCATION_MAX_INPUT_ACCURACY_M = 5000

async function loadCameraPlugin() {
    if (CameraPlugin) return CameraPlugin
    try {
        const mod = await import('@capacitor/camera')
        CameraPlugin = mod.Camera
        return CameraPlugin
    } catch {
        return null
    }
}

async function loadGeolocationPlugin() {
    if (GeolocationPlugin) return GeolocationPlugin
    try {
        const mod = await import('@capacitor/geolocation')
        GeolocationPlugin = mod.Geolocation
        return GeolocationPlugin
    } catch {
        return null
    }
}

/**
 * Check if app is running inside Capacitor native shell
 */
export function isNativeApp() {
    return Capacitor.isNativePlatform()
}

function isLocationGrantedStatus(status = {}) {
    return status.location === 'granted' || status.coarseLocation === 'granted'
}

function isLocationDeniedStatus(status = {}) {
    const preciseDenied = status.location === 'denied'
    const coarseDenied = status.coarseLocation === 'denied'
    return preciseDenied && (coarseDenied || status.coarseLocation == null)
}

function isLocationPromptStatus(status = {}) {
    return (
        status.location === 'prompt'
        || status.location === 'prompt-with-rationale'
        || status.coarseLocation === 'prompt'
        || status.coarseLocation === 'prompt-with-rationale'
    )
}

function isLocationPermissionDeniedError(error) {
    const code = String(error?.code || '').trim()
    const message = String(error?.message || '').trim()

    return (
        code === LOCATION_PERMISSION_DENIED_CODE
        || Number(error?.code) === WEB_GEOLOCATION_PERMISSION_DENIED_CODE
        || error?.name === 'NotAllowedError'
        || error?.name === 'PermissionDeniedError'
        || /permission request was denied|location access was denied|permission denied/i.test(message)
    )
}

function isLocationServicesDisabledError(error) {
    const code = String(error?.code || '').trim()
    const message = String(error?.message || '').trim()

    return (
        code === LOCATION_SERVICES_DISABLED_CODE
        || code === LOCATION_SETTINGS_DENIED_CODE
        || code === LOCATION_SETTINGS_ERROR_CODE
        || code === LOCATION_NETWORK_OFF_CODE
        || /location services?.*(disabled|enabled)|location settings|both network and location turned off/i.test(message)
    )
}

function isLocationTimeoutError(error) {
    const code = String(error?.code || '').trim()
    const message = String(error?.message || '').trim()

    return (
        code === LOCATION_TIMEOUT_CODE
        || Number(error?.code) === WEB_GEOLOCATION_TIMEOUT_CODE
        || /obtain location in time|timed out|timeout/i.test(message)
    )
}

function isLocationUnavailableError(error) {
    const message = String(error?.message || '').trim()

    return (
        Number(error?.code) === WEB_GEOLOCATION_POSITION_UNAVAILABLE_CODE
        || /position unavailable|unable to retrieve|unable to determine|could not determine/i.test(message)
    )
}

function getLocationErrorMessage(error, fallback = 'Unable to determine your location.') {
    if (isLocationServicesDisabledError(error)) {
        return 'Turn on your device location services, then try again.'
    }

    if (isLocationPermissionDeniedError(error)) {
        return isNativeApp()
            ? 'Location access was denied. Please enable it in your device Settings.'
            : 'Location access was denied. Please allow location access in your browser settings.'
    }

    if (isLocationTimeoutError(error)) {
        return 'Location is taking too long to resolve. Move to an open area, then try again.'
    }

    if (isLocationUnavailableError(error)) {
        return 'Your device could not determine a location. Check GPS, mobile data, or Wi-Fi and try again.'
    }

    const message = String(error?.message || '').trim()
    return message || fallback
}

function getLocationPermissionMessage(error) {
    return getLocationErrorMessage(error, 'Failed to request location permission.')
}

function buildPositionResult(position) {
    const coords = position?.coords || position || {}
    return {
        latitude: coords.latitude,
        longitude: coords.longitude,
        accuracy: typeof coords.accuracy === 'number' ? coords.accuracy : null,
        capturedAt: new Date().toISOString(),
    }
}

function cacheResolvedPosition(position) {
    if (!position) return null
    const normalized = buildPositionResult(position)
    lastResolvedPosition = {
        ...normalized,
        capturedAtMs: Date.now(),
    }
    return {
        latitude: normalized.latitude,
        longitude: normalized.longitude,
        accuracy: normalized.accuracy,
        capturedAt: normalized.capturedAt,
    }
}

function getCachedPosition(maxAgeMs = DEFAULT_LOCATION_CACHE_MAX_AGE_MS) {
    if (!lastResolvedPosition) return null
    const effectiveMaxAge = Number(maxAgeMs)
    if (!Number.isFinite(effectiveMaxAge) || effectiveMaxAge < 0) return null

    if (Date.now() - lastResolvedPosition.capturedAtMs > effectiveMaxAge) {
        return null
    }

    return {
        latitude: lastResolvedPosition.latitude,
        longitude: lastResolvedPosition.longitude,
        accuracy: lastResolvedPosition.accuracy,
        capturedAt: lastResolvedPosition.capturedAt,
    }
}

function resolveRequestedMaximumAge(options = {}, fallbackMs = DEFAULT_LOCATION_CACHE_MAX_AGE_MS) {
    const requested = Number(options?.maximumAge)
    if (Number.isFinite(requested) && requested >= 0) return requested
    return fallbackMs
}

function getWebSecureContextLocationError() {
    if (typeof window === 'undefined' || typeof window.isSecureContext !== 'boolean') {
        return null
    }

    if (window.isSecureContext) return null

    const hostname = String(window.location?.hostname || '').trim().toLowerCase()
    const isTrustedLocalhost =
        hostname === 'localhost'
        || hostname === '127.0.0.1'
        || hostname === '[::1]'

    if (isTrustedLocalhost) return null

    return 'Location access requires HTTPS or localhost in the browser.'
}

function requestBrowserCurrentPosition(options = {}) {
    return new Promise((resolve, reject) => {
        const secureContextError = getWebSecureContextLocationError()
        if (secureContextError) {
            reject(new Error(secureContextError))
            return
        }

        if (!navigator.geolocation) {
            reject(new Error('Geolocation is not supported by your browser.'))
            return
        }

        navigator.geolocation.getCurrentPosition(resolve, reject, options)
    })
}

async function getWebLocationPermissionState() {
    if (typeof navigator === 'undefined' || typeof navigator.permissions?.query !== 'function') {
        return null
    }

    try {
        const status = await navigator.permissions.query({ name: 'geolocation' })
        const state = String(status?.state || '').trim().toLowerCase()
        return state || null
    } catch {
        return null
    }
}

async function resolveNativeCurrentPosition(options = {}) {
    const cached = getCachedPosition(resolveRequestedMaximumAge(options))
    if (cached) return cached

    const permission = await requestLocationPermission()
    if (!permission.granted) {
        throw new Error(permission.message || 'Location access is required to continue.')
    }

    const Geolocation = await loadGeolocationPlugin()
    if (!Geolocation) {
        throw new Error('Geolocation plugin not available.')
    }

    const baseOptions = {
        ...DEFAULT_NATIVE_LOCATION_OPTIONS,
        ...options,
    }
    const attempts = [
        {
            ...baseOptions,
            timeout: Math.max(Number(baseOptions.timeout) || 0, 30000),
            maximumAge: Math.max(Number(baseOptions.maximumAge) || 0, 15000),
        },
        {
            ...baseOptions,
            enableHighAccuracy: false,
            timeout: Math.max(Number(baseOptions.timeout) || 0, 45000),
            maximumAge: Math.max(Number(baseOptions.maximumAge) || 0, 60000),
            enableLocationFallback: true,
        },
    ]

    let lastError = null

    for (const attempt of attempts) {
        try {
            const position = await Geolocation.getCurrentPosition(attempt)
            return cacheResolvedPosition(position)
        } catch (error) {
            lastError = error
            if (isLocationPermissionDeniedError(error) || isLocationServicesDisabledError(error)) {
                break
            }
        }
    }

    throw new Error(getLocationErrorMessage(lastError))
}

async function resolveWebCurrentPosition(options = {}) {
    const secureContextError = getWebSecureContextLocationError()
    if (secureContextError) {
        throw new Error(secureContextError)
    }

    if (!navigator.geolocation) {
        throw new Error('Geolocation is not supported by your browser.')
    }

    const cached = getCachedPosition(resolveRequestedMaximumAge(options))
    if (cached) return cached

    const permissionState = await getWebLocationPermissionState()
    if (permissionState === 'denied') {
        throw new Error('Location access was denied. Please allow location access in your browser settings.')
    }

    const baseOptions = {
        ...DEFAULT_WEB_LOCATION_OPTIONS,
        ...options,
    }
    const requestedTimeout = Number(baseOptions.timeout)
    const requestedMaximumAge = resolveRequestedMaximumAge(baseOptions, DEFAULT_WEB_LOCATION_OPTIONS.maximumAge)
    const initialTimeout = Number.isFinite(requestedTimeout)
        ? Math.min(Math.max(requestedTimeout, 4000), 12000)
        : DEFAULT_WEB_LOCATION_OPTIONS.timeout
    const attempts = [
        {
            ...baseOptions,
            timeout: initialTimeout,
            maximumAge: requestedMaximumAge,
        },
        {
            ...baseOptions,
            enableHighAccuracy: false,
            timeout: Math.max(Math.min(initialTimeout, 9000), 6000),
            maximumAge: Math.max(requestedMaximumAge, DEFAULT_LOCATION_CACHE_MAX_AGE_MS),
        },
    ]

    let lastError = null

    for (const attempt of attempts) {
        try {
            const position = await requestBrowserCurrentPosition(attempt)
            return cacheResolvedPosition(position)
        } catch (error) {
            lastError = error
            if (isLocationPermissionDeniedError(error)) {
                break
            }
        }
    }

    throw new Error(getLocationErrorMessage(lastError))
}

/**
 * Request camera permission.
 * Returns { granted: boolean, denied: boolean, message: string }
 */
export async function requestCameraPermission() {
    if (isNativeApp()) {
        try {
            const Camera = await loadCameraPlugin()
            if (!Camera) return { granted: false, denied: true, message: 'Camera plugin not available.' }

            const status = await Camera.checkPermissions()
            if (status.camera === 'granted') {
                return { granted: true, denied: false, message: '' }
            }

            const result = await Camera.requestPermissions({ permissions: ['camera'] })
            if (result.camera === 'granted') {
                return { granted: true, denied: false, message: '' }
            }

            return {
                granted: false,
                denied: true,
                message: 'Camera access was denied. Please enable it in your device Settings.',
            }
        } catch (error) {
            return {
                granted: false,
                denied: true,
                message: error?.message || 'Failed to request camera permission.',
            }
        }
    }

    // Web fallback
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true })
        stream.getTracks().forEach((track) => track.stop())
        return { granted: true, denied: false, message: '' }
    } catch (error) {
        const isDenied = error?.name === 'NotAllowedError' || error?.name === 'PermissionDeniedError'
        return {
            granted: false,
            denied: isDenied,
            message: isDenied
                ? 'Camera access was denied. Please allow camera access in your browser settings.'
                : 'Camera is not available on this device.',
        }
    }
}

/**
 * Request location permission.
 * Returns { granted: boolean, denied: boolean, message: string }
 */
export async function requestLocationPermission() {
    if (isNativeApp()) {
        try {
            const Geolocation = await loadGeolocationPlugin()
            if (!Geolocation) return { granted: false, denied: true, message: 'Geolocation plugin not available.' }

            const status = await Geolocation.checkPermissions()
            if (isLocationGrantedStatus(status)) {
                return { granted: true, denied: false, message: '' }
            }

            const result = await Geolocation.requestPermissions({ permissions: ['location', 'coarseLocation'] })
            if (isLocationGrantedStatus(result)) {
                return { granted: true, denied: false, message: '' }
            }

            return {
                granted: false,
                denied: isLocationDeniedStatus(result),
                message: isLocationPromptStatus(result)
                    ? 'Location access is required to continue. Please allow it on the next prompt.'
                    : 'Location access was denied. Please enable it in your device Settings.',
            }
        } catch (error) {
            return {
                granted: false,
                denied: isLocationPermissionDeniedError(error),
                message: getLocationPermissionMessage(error),
            }
        }
    }

    // Web fallback
    const secureContextError = getWebSecureContextLocationError()
    if (secureContextError) {
        return { granted: false, denied: true, message: secureContextError }
    }

    if (!navigator.geolocation) {
        return { granted: false, denied: true, message: 'Geolocation is not supported by your browser.' }
    }

    const permissionState = await getWebLocationPermissionState()
    if (permissionState === 'granted') {
        return { granted: true, denied: false, message: '' }
    }
    if (permissionState === 'denied') {
        return {
            granted: false,
            denied: true,
            message: 'Location access was denied. Please allow location access in your browser settings.',
        }
    }

    try {
        const position = await requestBrowserCurrentPosition({
            enableHighAccuracy: false,
            timeout: 7000,
            maximumAge: DEFAULT_LOCATION_CACHE_MAX_AGE_MS,
        })
        cacheResolvedPosition(position)
        return { granted: true, denied: false, message: '' }
    } catch (error) {
        const nextPermissionState = await getWebLocationPermissionState()
        const denied = nextPermissionState === 'denied' || isLocationPermissionDeniedError(error)

        return {
            granted: nextPermissionState === 'granted',
            denied,
            message: denied
                ? 'Location access was denied. Please allow location access in your browser settings.'
                : getLocationPermissionMessage(error),
        }
    }
}

/**
 * Get current position and throw a useful error when it cannot be retrieved.
 * Returns { latitude, longitude, accuracy }.
 */
export async function getCurrentPositionOrThrow(options = {}) {
    if (isNativeApp()) {
        return resolveNativeCurrentPosition(options)
    }

    return resolveWebCurrentPosition(options)
}

export async function getCurrentPositionWithinAccuracyOrThrow(options = {}) {
    const desiredAccuracy = Number(
        options.desiredAccuracy
        ?? options.targetAccuracy
        ?? options.maximumAcceptedAccuracy
    )

    if (!Number.isFinite(desiredAccuracy) || desiredAccuracy <= 0) {
        return getCurrentPositionOrThrow(options)
    }

    if (isNativeApp()) {
        return getCurrentPositionOrThrow(options)
    }

    const secureContextError = getWebSecureContextLocationError()
    if (secureContextError) {
        throw new Error(secureContextError)
    }

    if (!navigator?.geolocation) {
        throw new Error('Geolocation is not supported by your browser.')
    }

    const permissionState = await getWebLocationPermissionState()
    if (permissionState === 'denied') {
        throw new Error('Location access was denied. Please allow location access in your browser settings.')
    }

    const onAccuracyUpdate = typeof options.onAccuracyUpdate === 'function'
        ? options.onAccuracyUpdate
        : null
    const totalTimeout = Math.max(
        Number(options.timeout) || 0,
        DEFAULT_PRECISE_LOCATION_TIMEOUT_MS
    )

    return new Promise((resolve, reject) => {
        let settled = false
        let bestPosition = null
        let bestAccuracy = Number.POSITIVE_INFINITY
        let watchId = null
        let timeoutId = null

        const cleanup = () => {
            if (watchId != null) {
                navigator.geolocation.clearWatch(watchId)
            }

            if (timeoutId != null) {
                clearTimeout(timeoutId)
            }
        }

        const finishSuccess = (position) => {
            if (settled) return
            settled = true
            cleanup()
            resolve(cacheResolvedPosition(position))
        }

        const finishError = (message) => {
            if (settled) return
            settled = true
            cleanup()
            reject(new Error(message))
        }

        const handlePosition = (position) => {
            const accuracy = Number(position?.coords?.accuracy)
            if (!Number.isFinite(accuracy) || accuracy <= 0) {
                return
            }

            onAccuracyUpdate?.(accuracy)

            if (accuracy < bestAccuracy) {
                bestAccuracy = accuracy
                bestPosition = position
            }

            if (accuracy <= desiredAccuracy) {
                finishSuccess(position)
            }
        }

        const handleError = (error) => {
            finishError(getLocationErrorMessage(error))
        }

        watchId = navigator.geolocation.watchPosition(handlePosition, handleError, {
            enableHighAccuracy: options.enableHighAccuracy !== false,
            timeout: totalTimeout,
            maximumAge: 0,
        })

        timeoutId = setTimeout(() => {
            if (bestPosition && bestAccuracy <= DEFAULT_PRECISE_LOCATION_MAX_INPUT_ACCURACY_M) {
                finishError(
                    `GPS accuracy is still ${Math.round(bestAccuracy)}m. Enable precise location and wait for a stronger GPS signal before signing in.`
                )
                return
            }

            if (bestPosition) {
                finishError(
                    `GPS accuracy is ${Math.round(bestAccuracy)}m. The device is only providing an approximate location right now.`
                )
                return
            }

            finishError('Location lookup timed out. Try again.')
        }, totalTimeout)
    })
}

/**
 * Get current position using native GPS or web fallback.
 * Returns { latitude, longitude, accuracy } or null on error.
 */
export async function getCurrentPosition(options = {}) {
    try {
        return await getCurrentPositionOrThrow(options)
    } catch {
        return null
    }
}

export async function primeLocationAccess(options = {}) {
    const cached = getCachedPosition(resolveRequestedMaximumAge(options))
    if (cached) return cached

    if (!isNativeApp()) {
        const secureContextError = getWebSecureContextLocationError()
        if (secureContextError || !navigator?.geolocation) {
            return null
        }

        try {
            const position = await requestBrowserCurrentPosition({
                ...DEFAULT_LOCATION_PRIME_OPTIONS,
                ...options,
            })
            return cacheResolvedPosition(position)
        } catch {
            return null
        }
    }

    try {
        return await getCurrentPositionOrThrow({
            ...DEFAULT_LOCATION_PRIME_OPTIONS,
            ...options,
        })
    } catch {
        return null
    }
}
