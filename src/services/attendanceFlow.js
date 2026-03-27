const MANILA_OFFSET_SUFFIX = '+08:00'
const TIMEZONE_PATTERN = /([zZ]|[+-]\d{2}:\d{2})$/

function normalizeLower(value) {
    return String(value || '').trim().toLowerCase()
}

function clampMinutes(value) {
    const normalized = Number(value)
    return Number.isFinite(normalized) ? Math.max(0, normalized) : 0
}

export function parseEventDateTime(value) {
    if (!value) return new Date(Number.NaN)

    const normalizedValue = TIMEZONE_PATTERN.test(String(value))
        ? String(value)
        : `${value}${MANILA_OFFSET_SUFFIX}`

    return new Date(normalizedValue)
}

function hasValidAttendanceOverride(event = {}) {
    if (!event?.present_until_override_at || !event?.late_until_override_at) {
        return false
    }

    const start = parseEventDateTime(event.start_datetime)
    const presentUntil = parseEventDateTime(event.present_until_override_at)
    const lateUntil = parseEventDateTime(event.late_until_override_at)

    if (
        !Number.isFinite(start.getTime())
        || !Number.isFinite(presentUntil.getTime())
        || !Number.isFinite(lateUntil.getTime())
    ) {
        return false
    }

    return (
        presentUntil.getTime() > start.getTime()
        && lateUntil.getTime() >= presentUntil.getTime()
    )
}

function getEffectivePresentCutoff(event = {}) {
    if (hasValidAttendanceOverride(event) && event.present_until_override_at) {
        return parseEventDateTime(event.present_until_override_at)
    }

    return parseEventDateTime(event.start_datetime)
}

function getEffectiveLateCutoff(event = {}) {
    if (hasValidAttendanceOverride(event) && event.late_until_override_at) {
        return parseEventDateTime(event.late_until_override_at)
    }

    const start = parseEventDateTime(event.start_datetime)
    return new Date(start.getTime() + clampMinutes(event.late_threshold_minutes) * 60_000)
}

function getSignOutOpenTime(event = {}) {
    const end = parseEventDateTime(event.end_datetime)
    return new Date(end.getTime() + clampMinutes(event.sign_out_open_delay_minutes) * 60_000)
}

function getSignOutCloseTime(event = {}) {
    const end = parseEventDateTime(event.end_datetime)
    const defaultClose = new Date(end.getTime() + clampMinutes(event.sign_out_grace_minutes) * 60_000)
    const overrideClose = parseEventDateTime(event.sign_out_override_until)

    if (Number.isFinite(overrideClose.getTime())) {
        return overrideClose.getTime() < defaultClose.getTime()
            ? overrideClose
            : defaultClose
    }

    return defaultClose
}

export function normalizeEventStatus(value) {
    const normalized = normalizeLower(value)
    return normalized === 'done' ? 'completed' : normalized
}

export function normalizeEventTimeStatusValue(timeStatus) {
    if (timeStatus && typeof timeStatus === 'object') {
        return normalizeLower(timeStatus.event_status ?? timeStatus.status)
    }

    return normalizeLower(timeStatus)
}

export function mapEventTimeStatusToEventStatus(timeStatus) {
    const normalizedTimeStatus = normalizeEventTimeStatusValue(timeStatus)

    if (['before_check_in', 'early_check_in'].includes(normalizedTimeStatus)) {
        return 'upcoming'
    }

    if (['late_check_in', 'absent_check_in', 'sign_out_pending', 'sign_out_open'].includes(normalizedTimeStatus)) {
        return 'ongoing'
    }

    if (normalizedTimeStatus === 'closed') {
        return 'completed'
    }

    return null
}

export function resolveEventLifecycleStatus(event = null, timeStatus = null) {
    const mappedStatus = mapEventTimeStatusToEventStatus(timeStatus)
    if (mappedStatus) return mappedStatus
    return normalizeEventStatus(event?.status)
}

export function resolveEventTimeStatusMoment(value) {
    const parsedValue = parseEventDateTime(value)
    return Number.isFinite(parsedValue.getTime()) ? parsedValue : null
}

export function resolveSignOutOpenDate(event = null, timeStatus = null) {
    const backendSignOutOpen = resolveEventTimeStatusMoment(timeStatus?.sign_out_opens_at)
    if (backendSignOutOpen) return backendSignOutOpen

    if (!event?.end_datetime) return null

    const fallbackSignOutOpen = getSignOutOpenTime(event)
    return Number.isFinite(fallbackSignOutOpen.getTime()) ? fallbackSignOutOpen : null
}

export function getMillisecondsUntilSignOutOpen({
    event = null,
    timeStatus = null,
    now = new Date(),
}) {
    const signOutOpenAt = resolveSignOutOpenDate(event, timeStatus)
    if (!signOutOpenAt) return null

    const effectiveNow = resolveEventTimeStatusMoment(timeStatus?.current_time) || now
    const diffMs = signOutOpenAt.getTime() - effectiveNow.getTime()
    return Number.isFinite(diffMs) ? diffMs : null
}

export function formatCompactDuration(value) {
    const normalizedValue = Number(value)
    if (!Number.isFinite(normalizedValue)) return ''

    const totalMinutes = Math.max(0, Math.ceil(normalizedValue / 60_000))
    if (totalMinutes <= 0) {
        return 'less than 1 min'
    }

    const hours = Math.floor(totalMinutes / 60)
    const minutes = totalMinutes % 60

    if (hours > 0 && minutes > 0) {
        return `${hours}h ${minutes}m`
    }

    if (hours > 0) {
        return `${hours}h`
    }

    return `${minutes}m`
}

export function resolveEventWindowStage(event = null, timeStatus = null, now = new Date()) {
    const normalizedTimeStatus = normalizeEventTimeStatusValue(timeStatus)
    if (normalizedTimeStatus) {
        const currentTimeMs = now.getTime()

        if (Number.isFinite(currentTimeMs)) {
            const signOutOpenAt = resolveSignOutOpenDate(event, timeStatus)
            const signOutCloseAt =
                resolveEventTimeStatusMoment(timeStatus?.effective_sign_out_closes_at)
                || (event?.end_datetime ? getSignOutCloseTime(event) : null)

            if (normalizedTimeStatus === 'sign_out_pending' && signOutOpenAt) {
                if (signOutCloseAt && currentTimeMs > signOutCloseAt.getTime()) {
                    return 'closed'
                }

                if (currentTimeMs >= signOutOpenAt.getTime()) {
                    return 'sign_out_open'
                }
            }

            if (normalizedTimeStatus === 'sign_out_open' && signOutCloseAt && currentTimeMs > signOutCloseAt.getTime()) {
                return 'closed'
            }
        }

        return normalizedTimeStatus
    }
    if (!event?.start_datetime || !event?.end_datetime) return ''

    const start = parseEventDateTime(event.start_datetime)
    const end = parseEventDateTime(event.end_datetime)
    const earlyCheckInOpensAt = new Date(
        start.getTime() - clampMinutes(event.early_check_in_minutes) * 60_000
    )
    const effectivePresentCutoff = getEffectivePresentCutoff(event)
    const effectiveLateCutoff = getEffectiveLateCutoff(event)
    const signOutOpenTime = getSignOutOpenTime(event)
    const effectiveSignOutClose = getSignOutCloseTime(event)
    const nowMs = now.getTime()

    if (!Number.isFinite(nowMs)) return ''
    if (nowMs < earlyCheckInOpensAt.getTime()) return 'before_check_in'
    if (nowMs < effectivePresentCutoff.getTime()) return 'early_check_in'
    if (nowMs >= signOutOpenTime.getTime()) {
        return nowMs <= effectiveSignOutClose.getTime() ? 'sign_out_open' : 'closed'
    }
    if (nowMs >= end.getTime()) return 'sign_out_pending'
    if (nowMs <= effectiveLateCutoff.getTime()) return 'late_check_in'
    return 'absent_check_in'
}

export function hasSignedInAttendance(attendanceRecord) {
    return Boolean(attendanceRecord?.time_in)
}

export function hasSignedOutAttendance(attendanceRecord) {
    return Boolean(attendanceRecord?.time_out)
}

export function getAttendanceRecordTimestamp(attendanceRecord) {
    const rawValue =
        attendanceRecord?.time_in
        || attendanceRecord?.created_at
        || attendanceRecord?.updated_at

    if (!rawValue) return 0

    const parsedValue = new Date(rawValue)
    return Number.isNaN(parsedValue.getTime()) ? 0 : parsedValue.getTime()
}

export function isOpenAttendanceRecord(attendanceRecord) {
    return hasSignedInAttendance(attendanceRecord) && !hasSignedOutAttendance(attendanceRecord)
}

export function resolveAttendanceCompletionState(attendanceRecord) {
    const normalizedCompletionState = normalizeLower(attendanceRecord?.completion_state)
    if (normalizedCompletionState === 'completed' || normalizedCompletionState === 'incomplete') {
        return normalizedCompletionState
    }

    if (hasSignedOutAttendance(attendanceRecord)) return 'completed'
    if (hasSignedInAttendance(attendanceRecord)) return 'incomplete'
    return ''
}

export function resolveAttendanceDisplayStatus(attendanceRecord) {
    const normalizedDisplayStatus = normalizeLower(attendanceRecord?.display_status)
    if (normalizedDisplayStatus) return normalizedDisplayStatus

    if (resolveAttendanceCompletionState(attendanceRecord) !== 'completed') {
        return hasSignedInAttendance(attendanceRecord) ? 'incomplete' : ''
    }

    const normalizedStoredStatus = normalizeLower(attendanceRecord?.status)
    if (['present', 'late', 'absent', 'excused'].includes(normalizedStoredStatus)) {
        return normalizedStoredStatus
    }

    return hasSignedOutAttendance(attendanceRecord) ? 'absent' : ''
}

export function isValidCompletedAttendanceRecord(attendanceRecord) {
    if (!attendanceRecord) return false

    if (typeof attendanceRecord.is_valid_attendance === 'boolean') {
        return attendanceRecord.is_valid_attendance
    }

    if (resolveAttendanceCompletionState(attendanceRecord) !== 'completed') {
        return false
    }

    return ['present', 'late'].includes(normalizeLower(attendanceRecord?.status))
}

export function getLatestAttendanceRecordsByEvent(attendanceRecords = []) {
    if (!Array.isArray(attendanceRecords) || !attendanceRecords.length) return []

    const latestByEvent = new Map()

    attendanceRecords
        .map((record) => ({
            record,
            timestamp: getAttendanceRecordTimestamp(record),
        }))
        .sort((left, right) => right.timestamp - left.timestamp)
        .forEach(({ record }) => {
            const eventId = Number(record?.event_id)
            if (!Number.isFinite(eventId) || latestByEvent.has(eventId)) return
            latestByEvent.set(eventId, record)
        })

    return Array.from(latestByEvent.values())
}

export function isResolvedAttendanceRecord(attendanceRecord) {
    if (!attendanceRecord) return false
    if (isOpenAttendanceRecord(attendanceRecord)) return false

    const completionState = resolveAttendanceCompletionState(attendanceRecord)
    if (completionState === 'completed') return true

    const status = normalizeLower(attendanceRecord.status)
    return hasSignedOutAttendance(attendanceRecord) || ['present', 'late', 'absent', 'excused'].includes(status)
}

export function isEventReadyForSignOut(eventStatus, timeStatus, event = null) {
    return resolveEventWindowStage(event ?? { status: eventStatus }, timeStatus) === 'sign_out_open'
}

export function resolveAttendanceActionState({
    event = null,
    eventStatus,
    attendanceRecord,
    timeStatus = null,
    now = new Date(),
}) {
    if (isResolvedAttendanceRecord(attendanceRecord)) {
        return 'done'
    }

    const stage = resolveEventWindowStage(event ?? { status: eventStatus }, timeStatus, now)

    if (isOpenAttendanceRecord(attendanceRecord)) {
        if (stage === 'sign_out_open') return 'sign-out'
        if (stage === 'closed') return 'closed'
        return 'waiting-sign-out'
    }

    if (['early_check_in', 'late_check_in', 'absent_check_in'].includes(stage)) {
        return 'sign-in'
    }

    if (stage === 'before_check_in') {
        return 'not-open'
    }

    if (stage === 'sign_out_open') {
        return 'missed-check-in'
    }

    if (stage === 'sign_out_pending' || stage === 'closed') {
        return 'closed'
    }

    return normalizeEventStatus(eventStatus) === 'ongoing'
        ? 'sign-in'
        : 'closed'
}

export function buildAttendanceLocationErrorMessage(detail) {
    if (!detail || typeof detail !== 'object') {
        return 'Location verification failed.'
    }

    const accuracy = detail.accuracy_m
    const formattedAccuracy = typeof accuracy === 'number' && Number.isFinite(accuracy)
        ? `${Math.round(accuracy)}m`
        : 'too low'
    const reason = typeof detail.reason === 'string' ? detail.reason.trim() : ''
    const distance = Number(detail.distance_m)
    const radius = Number(detail.radius_m)
    const hasDistanceSummary = Number.isFinite(distance) && Number.isFinite(radius)
    const distanceSummary = hasDistanceSummary
        ? `You are ${distance.toFixed(1)}m away. Stay within ${radius.toFixed(0)}m of the event location.`
        : ''

    if (reason) {
        if (reason.startsWith('gps_accuracy_too_low:')) {
            return `GPS accuracy is ${formattedAccuracy}. Enable precise location and wait for a stronger GPS signal before signing in.`
        }

        if (reason === 'gps_accuracy_missing' || reason === 'accuracy_missing') {
            return 'This event requires a precise GPS reading, but the browser did not provide one.'
        }

        if (reason === 'gps_accuracy_invalid' || reason === 'invalid_accuracy') {
            return 'The device returned an invalid GPS accuracy reading. Try again after refreshing location services.'
        }

        if (reason === 'gps_accuracy_too_low' || reason === 'accuracy_exceeds_limit') {
            return `GPS accuracy is ${formattedAccuracy}. Enable precise location and wait for a stronger GPS signal before signing in.`
        }

        if (reason === 'outside_geofence_with_uncertainty' || reason === 'outside_geofence_buffered') {
            return hasDistanceSummary
                ? `${distanceSummary} Your current GPS signal is too weak to confirm that you are inside the event area.`
                : 'Your current GPS signal is too weak to confirm that you are inside the event area.'
        }

        if (reason === 'outside_geofence') {
            return hasDistanceSummary ? distanceSummary : 'You are outside the allowed event location.'
        }

        if (reason === 'invalid_user_coordinates') {
            return 'The device returned an invalid location reading. Refresh location services and try again.'
        }

        if (reason === 'invalid_event_coordinates') {
            return 'This event has an invalid location setup. Ask the organizer to update the event map marker.'
        }

        if (reason === 'invalid_geofence_radius' || reason === 'geofence_radius_out_of_range') {
            return 'This event geofence is not configured correctly. Ask the organizer to update the event radius.'
        }

        return reason
    }

    if (hasDistanceSummary) {
        return distanceSummary
    }

    return 'Location verification failed.'
}
