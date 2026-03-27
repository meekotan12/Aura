import {
    isNgrokApiBaseUrl,
    resolveAbsoluteApiBaseUrl,
    resolveApiBaseUrl,
    resolveApiTimeoutMs,
} from '@/services/backendBaseUrl.js'

function toOptionalString(value, fallback = '') {
    if (value == null) return fallback
    const normalized = String(value).trim()
    return normalized.length ? normalized : fallback
}

function toOptionalNumber(value, fallback = null) {
    const normalized = Number(value)
    return Number.isFinite(normalized) ? normalized : fallback
}

function normalizeLiveness(payload = null) {
    if (!payload || typeof payload !== 'object') return null

    return {
        ...payload,
        label: toOptionalString(payload.label, null),
        score: toOptionalNumber(payload.score, null),
        reason: toOptionalString(payload.reason, null),
    }
}

function normalizeOutcome(payload = {}) {
    return {
        ...payload,
        action: toOptionalString(payload.action, 'rejected'),
        reason_code: toOptionalString(payload.reason_code, null),
        message: toOptionalString(payload.message, 'Public attendance scan finished.'),
        student_id: toOptionalString(payload.student_id, null),
        student_name: toOptionalString(payload.student_name, null),
        attendance_id: toOptionalNumber(payload.attendance_id, null),
        distance: toOptionalNumber(payload.distance, null),
        confidence: toOptionalNumber(payload.confidence, null),
        threshold: toOptionalNumber(payload.threshold, null),
        liveness: normalizeLiveness(payload.liveness),
        time_in: toOptionalString(payload.time_in, null),
        time_out: toOptionalString(payload.time_out, null),
        duration_minutes: toOptionalNumber(payload.duration_minutes, null),
    }
}

function normalizeEvent(payload = {}) {
    return {
        ...payload,
        id: toOptionalNumber(payload.id, 0),
        school_id: toOptionalNumber(payload.school_id, 0),
        school_name: toOptionalString(payload.school_name, 'Campus'),
        name: toOptionalString(payload.name, 'Untitled Event'),
        location: toOptionalString(payload.location, 'TBA'),
        start_datetime: toOptionalString(payload.start_datetime, null),
        end_datetime: toOptionalString(payload.end_datetime, null),
        geo_radius_m: toOptionalNumber(payload.geo_radius_m, 0),
        distance_m: toOptionalNumber(payload.distance_m, null),
        effective_distance_m: toOptionalNumber(payload.effective_distance_m, null),
        accuracy_m: toOptionalNumber(payload.accuracy_m, null),
        attendance_phase: toOptionalString(payload.attendance_phase, 'sign_in'),
        phase_message: toOptionalString(payload.phase_message, ''),
        scope_label: toOptionalString(payload.scope_label, 'Campus-wide'),
        departments: Array.isArray(payload.departments) ? payload.departments.map((item) => toOptionalString(item, '')).filter(Boolean) : [],
        programs: Array.isArray(payload.programs) ? payload.programs.map((item) => toOptionalString(item, '')).filter(Boolean) : [],
    }
}

function normalizeNearbyEventsResponse(payload = {}) {
    return {
        events: Array.isArray(payload.events) ? payload.events.map(normalizeEvent) : [],
        scan_cooldown_seconds: Math.max(0, toOptionalNumber(payload.scan_cooldown_seconds, 8) ?? 8),
    }
}

function normalizeScanResponse(payload = {}) {
    return {
        ...payload,
        event_id: toOptionalNumber(payload.event_id, 0),
        event_phase: toOptionalString(payload.event_phase, 'sign_in'),
        message: toOptionalString(payload.message, 'Public attendance scan finished.'),
        scan_cooldown_seconds: Math.max(0, toOptionalNumber(payload.scan_cooldown_seconds, 8) ?? 8),
        geo: payload.geo && typeof payload.geo === 'object' ? { ...payload.geo } : null,
        outcomes: Array.isArray(payload.outcomes) ? payload.outcomes.map(normalizeOutcome) : [],
    }
}

function buildUrl(path, params = null) {
    const apiBaseUrl = resolveApiBaseUrl()
    const url = new URL(`${resolveAbsoluteApiBaseUrl(apiBaseUrl)}${path}`)

    if (params && typeof params === 'object') {
        Object.entries(params).forEach(([key, value]) => {
            if (value == null || value === '') return
            url.searchParams.set(key, String(value))
        })
    }

    return {
        apiBaseUrl,
        url: url.toString(),
    }
}

async function parsePublicResponse(response) {
    const contentType = response.headers.get('content-type') || ''
    const isJson = contentType.includes('application/json')

    let payload = null
    try {
        payload = isJson ? await response.json() : await response.text()
    } catch {
        payload = null
    }

    if (!response.ok) {
        const detail = payload?.detail ?? payload?.message ?? payload
        const message =
            detail?.message
            || detail?.reason
            || detail
            || response.statusText
            || 'Request failed.'

        throw new PublicAttendanceApiError(String(message), {
            status: response.status,
            detail,
        })
    }

    return payload
}

async function requestPublic(path, options = {}) {
    const {
        method = 'GET',
        headers = {},
        body,
        params = null,
    } = options

    const timeoutMs = resolveApiTimeoutMs()
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

    const { apiBaseUrl, url } = buildUrl(path, params)

    try {
        const response = await fetch(url, {
            method,
            signal: controller.signal,
            headers: {
                ...(isNgrokApiBaseUrl(apiBaseUrl) ? { 'ngrok-skip-browser-warning': 'true' } : {}),
                ...headers,
            },
            body,
        })

        return await parsePublicResponse(response)
    } catch (error) {
        if (error?.name === 'AbortError') {
            throw new PublicAttendanceApiError(
                `The public attendance service took too long to respond. (${timeoutMs}ms timeout)`,
                {
                    detail: {
                        timeoutMs,
                        path,
                    },
                }
            )
        }

        if (error instanceof PublicAttendanceApiError) {
            throw error
        }

        throw new PublicAttendanceApiError(
            'Unable to reach the public attendance service.',
            {
                detail: {
                    cause: error?.message || null,
                    path,
                },
            }
        )
    } finally {
        clearTimeout(timeoutId)
    }
}

function blobToDataUrl(blob) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(String(reader.result))
        reader.onerror = () => reject(new Error('Failed to read the camera frame.'))
        reader.readAsDataURL(blob)
    })
}

export class PublicAttendanceApiError extends Error {
    constructor(message, { status = 0, detail = null } = {}) {
        super(message)
        this.name = 'PublicAttendanceApiError'
        this.status = status
        this.detail = detail
    }
}

export function resolvePublicAttendanceRetryAfterMs(error, fallbackMs = 1400) {
    const retryAfterSeconds = Number(error?.detail?.retry_after_seconds)
    if (Number.isFinite(retryAfterSeconds) && retryAfterSeconds > 0) {
        return Math.max(500, Math.ceil(retryAfterSeconds * 1000))
    }

    return fallbackMs
}

export function describePublicAttendanceError(error) {
    if (error instanceof PublicAttendanceApiError) {
        const detail = error.detail
        if (typeof detail === 'string' && detail.trim()) {
            return detail
        }

        if (detail && typeof detail === 'object') {
            const message = toOptionalString(detail.message, '')
            if (message) return message

            const reason = toOptionalString(detail.reason, '')
            if (reason) return reason
        }

        return error.message
    }

    return error instanceof Error
        ? error.message
        : 'The public attendance kiosk request failed.'
}

export async function fetchNearbyPublicAttendanceEvents(location) {
    const payload = await requestPublic('/public-attendance/events/nearby', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            latitude: Number(location?.latitude),
            longitude: Number(location?.longitude),
            accuracy_m: location?.accuracyM ?? null,
        }),
    })

    return normalizeNearbyEventsResponse(payload)
}

export async function submitPublicAttendanceScan({
    eventId,
    imageBlob,
    location,
    cooldownStudentIds = [],
    threshold = null,
}) {
    const imageBase64 = await blobToDataUrl(imageBlob)

    const payload = await requestPublic(`/public-attendance/events/${eventId}/multi-face-scan`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            image_base64: imageBase64,
            latitude: Number(location?.latitude),
            longitude: Number(location?.longitude),
            accuracy_m: location?.accuracyM ?? null,
            threshold,
            cooldown_student_ids: Array.isArray(cooldownStudentIds) ? cooldownStudentIds : [],
        }),
    })

    return normalizeScanResponse(payload)
}
