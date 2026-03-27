const EVENT_STATUS_VALUES = ['upcoming', 'ongoing', 'completed', 'cancelled']

export const EVENT_STATUS_OPTIONS = [
    { value: 'upcoming', label: 'Upcoming' },
    { value: 'ongoing', label: 'Ongoing' },
    { value: 'completed', label: 'Completed' },
    { value: 'cancelled', label: 'Cancelled' },
]

function normalizeStatusValue(value) {
    const normalized = String(value || '').trim().toLowerCase()
    if (normalized === 'done') return 'completed'
    return EVENT_STATUS_VALUES.includes(normalized) ? normalized : 'upcoming'
}

export function toOptionalFiniteNumber(value) {
    if (value == null || value === '') return null
    const normalized = Number(value)
    return Number.isFinite(normalized) ? normalized : null
}

export function toOptionalNonNegativeInteger(value, fallback = 0) {
    if (value == null || value === '') return fallback
    const normalized = Number(value)
    if (!Number.isFinite(normalized)) return fallback
    return Math.max(0, Math.round(normalized))
}

export function toBackendDateTimeValue(value) {
    return String(value || '').trim()
}

export function toLocalDateTimeInputValue(value) {
    const normalized = String(value || '').trim()
    if (!normalized) return ''

    const match = normalized.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/)
    if (match) {
        return `${match[1]}T${match[2]}`
    }

    const parsed = new Date(normalized)
    if (!Number.isFinite(parsed.getTime())) return ''

    const year = parsed.getFullYear()
    const month = `${parsed.getMonth() + 1}`.padStart(2, '0')
    const day = `${parsed.getDate()}`.padStart(2, '0')
    const hours = `${parsed.getHours()}`.padStart(2, '0')
    const minutes = `${parsed.getMinutes()}`.padStart(2, '0')
    return `${year}-${month}-${day}T${hours}:${minutes}`
}

export function createEventEditorDraft(event = null) {
    return {
        name: String(event?.name || '').trim(),
        location: String(event?.location || '').trim(),
        startTime: toLocalDateTimeInputValue(event?.start_datetime ?? event?.start_time),
        endTime: toLocalDateTimeInputValue(event?.end_datetime ?? event?.end_time),
        status: normalizeStatusValue(event?.status),
        geoRequired: Boolean(event?.geo_required),
        latitude: event?.geo_latitude ?? '',
        longitude: event?.geo_longitude ?? '',
        radiusM: event?.geo_radius_m ?? '',
        maxAccuracyM: event?.geo_max_accuracy_m ?? '',
        earlyCheckInMinutes: event?.early_check_in_minutes ?? 0,
        lateThresholdMinutes: event?.late_threshold_minutes ?? 0,
        signOutGraceMinutes: event?.sign_out_grace_minutes ?? 0,
        signOutOpenDelayMinutes: event?.sign_out_open_delay_minutes ?? 0,
    }
}

export function validateEventEditorDraft(draft) {
    const name = String(draft?.name || '').trim()
    const location = String(draft?.location || '').trim()
    const startTime = new Date(String(draft?.startTime || '').trim())
    const endTime = new Date(String(draft?.endTime || '').trim())

    if (!name) {
        throw new Error('Event name is required.')
    }

    if (!location) {
        throw new Error('Event location is required.')
    }

    if (!Number.isFinite(startTime.getTime()) || !Number.isFinite(endTime.getTime())) {
        throw new Error('Please provide valid start and end dates.')
    }

    if (endTime <= startTime) {
        throw new Error('The event end time must be later than the start time.')
    }

    const geoLatitude = toOptionalFiniteNumber(draft?.latitude)
    const geoLongitude = toOptionalFiniteNumber(draft?.longitude)
    const geoRadius = toOptionalFiniteNumber(draft?.radiusM)
    const providedGeoFields = [geoLatitude != null, geoLongitude != null, geoRadius != null]

    if (providedGeoFields.some(Boolean) && !providedGeoFields.every(Boolean)) {
        throw new Error('Latitude, longitude, and radius must be provided together for the event geofence.')
    }

    if (Boolean(draft?.geoRequired) && !providedGeoFields.every(Boolean)) {
        throw new Error('Geofence coordinates and radius are required when geolocation is enabled.')
    }

    const signOutGraceMinutes = toOptionalNonNegativeInteger(draft?.signOutGraceMinutes, 0)
    const signOutOpenDelayMinutes = toOptionalNonNegativeInteger(draft?.signOutOpenDelayMinutes, 0)

    if (signOutOpenDelayMinutes > signOutGraceMinutes) {
        throw new Error('Sign-out open delay cannot be greater than sign-out grace minutes.')
    }
}

export function buildEventUpdatePayloadFromDraft(draft) {
    validateEventEditorDraft(draft)

    return {
        name: String(draft?.name || '').trim(),
        location: String(draft?.location || '').trim(),
        start_datetime: toBackendDateTimeValue(draft?.startTime),
        end_datetime: toBackendDateTimeValue(draft?.endTime),
        status: normalizeStatusValue(draft?.status),
        geo_required: Boolean(draft?.geoRequired),
        geo_latitude: toOptionalFiniteNumber(draft?.latitude),
        geo_longitude: toOptionalFiniteNumber(draft?.longitude),
        geo_radius_m: toOptionalFiniteNumber(draft?.radiusM),
        geo_max_accuracy_m: toOptionalFiniteNumber(draft?.maxAccuracyM),
        early_check_in_minutes: toOptionalNonNegativeInteger(draft?.earlyCheckInMinutes, 0),
        late_threshold_minutes: toOptionalNonNegativeInteger(draft?.lateThresholdMinutes, 0),
        sign_out_grace_minutes: toOptionalNonNegativeInteger(draft?.signOutGraceMinutes, 0),
        sign_out_open_delay_minutes: toOptionalNonNegativeInteger(draft?.signOutOpenDelayMinutes, 0),
    }
}
