import {
    isNgrokApiBaseUrl,
    resolveAbsoluteApiBaseUrl,
    resolveApiBaseUrl,
    resolveApiTimeoutMs,
} from '@/services/backendBaseUrl.js'
import {
    normalizeAuditLogResponse,
    normalizeCreateSchoolWithSchoolItResponse,
    normalizeAttendanceRecord,
    normalizeDepartment,
    normalizeGovernanceRequest,
    normalizeGovernanceSetting,
    normalizeEvent,
    normalizeEventAttendanceReport,
    normalizeEventAttendanceWithStudent,
    normalizeEventLocationResponse,
    normalizeEventTimeStatus,
    normalizeFaceReferenceResponse,
    normalizeFaceStatus,
    normalizeFaceVerificationResponse,
    normalizeGovernanceMember,
    normalizeGovernanceSsgSetup,
    normalizeGovernanceStudentCandidate,
    normalizeGovernanceUnitDetail,
    normalizeNotificationDispatchSummary,
    normalizeNotificationLogItem,
    normalizePasswordChangeResponse,
    normalizePasswordResetResponse,
    normalizeProgram,
    normalizeSchoolSettings,
    normalizeSchoolSummary,
    normalizeSchoolItAccount,
    normalizeStudentFaceRegistrationResponse,
    normalizeTokenPayload,
    normalizeRetentionRunResult,
    normalizeUserCreateResponse,
    normalizeUserWithRelations,
} from '@/services/backendNormalizers.js'
import {
    normalizeImportJobCreateResponse,
    normalizeImportJobStatus,
    normalizeImportPreviewSummary,
} from '@/services/studentImport.js'
import { notifySessionExpired } from '@/services/sessionExpiry.js'

export class BackendApiError extends Error {
    constructor(message, { status = 0, details = null } = {}) {
        super(message)
        this.name = 'BackendApiError'
        this.status = status
        this.details = details
    }
}

export { resolveApiBaseUrl }

function buildUrl(baseUrl, path, params) {
    const url = new URL(`${resolveAbsoluteApiBaseUrl(baseUrl)}${path}`)

    if (params) {
        Object.entries(params).forEach(([key, value]) => {
            if (value == null || value === '') return
            url.searchParams.set(key, String(value))
        })
    }

    return url.toString()
}

async function parseResponse(response) {
    const contentType = response.headers.get('content-type') || ''
    const isJson = contentType.includes('application/json')

    let payload = null
    try {
        payload = isJson ? await response.json() : await response.text()
    } catch {
        payload = null
    }

    if (!response.ok) {
        const message =
            payload?.detail?.message ||
            payload?.detail ||
            payload?.message ||
            response.statusText ||
            'Request failed.'
        throw new BackendApiError(String(message), {
            status: response.status,
            details: payload,
        })
    }

    if (!isJson) {
        const textPayload = typeof payload === 'string' ? payload.trim() : ''
        const isEmptyBody =
            response.status === 204 ||
            response.status === 205 ||
            textPayload.length === 0

        if (isEmptyBody) {
            return null
        }

        throw new BackendApiError('The API returned an unexpected non-JSON response.', {
            status: response.status,
            details: {
                kind: 'unexpected_non_json',
                contentType,
                payload: textPayload,
            },
        })
    }

    return payload
}

function shouldRetryWithApiProxyPrefix(path, error) {
    return (
        typeof path === 'string'
        && path.startsWith('/api/')
        && !path.startsWith('/api/api/')
        && error instanceof BackendApiError
        && (
            Number(error.status) === 404 ||
            error?.details?.kind === 'unexpected_non_json'
        )
    )
}

function buildProxyCompatibleApiPath(path) {
    return path.startsWith('/api/') ? `/api${path}` : path
}

function maybeHandleSessionExpiry(error, token, suppressSessionExpiryHandling) {
    if (
        token &&
        !suppressSessionExpiryHandling &&
        error instanceof BackendApiError &&
        Number(error.status) === 401
    ) {
        notifySessionExpired()
    }
}

async function performRequest(baseUrl, path, options = {}) {
    const {
        token,
        params,
        headers = {},
        body,
        ...rest
    } = options

    const timeoutMs = resolveApiTimeoutMs()
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

    let response
    try {
        response = await fetch(buildUrl(baseUrl, path, params), {
            ...rest,
            signal: controller.signal,
            headers: {
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
                ...(isNgrokApiBaseUrl(baseUrl) ? { 'ngrok-skip-browser-warning': 'true' } : {}),
                ...headers,
            },
            body,
        })
    } catch (error) {
        if (error?.name === 'AbortError') {
            throw new BackendApiError(
                `The API took too long to respond. The backend or ngrok tunnel may be offline. (${timeoutMs}ms timeout)`,
                {
                    details: {
                        path,
                        timeoutMs,
                    },
                }
            )
        }

        throw new BackendApiError(
            'Unable to reach the API. The server may be unavailable or the request may be blocked.',
            {
                details: {
                    cause: error?.message || null,
                    path,
                },
            }
        )
    } finally {
        clearTimeout(timeoutId)
    }

    return parseResponse(response)
}

async function request(baseUrl, path, options = {}) {
    const {
        token,
        suppressSessionExpiryHandling = false,
        ...rest
    } = options

    try {
        return await performRequest(baseUrl, path, {
            token,
            suppressSessionExpiryHandling,
            ...rest,
        })
    } catch (error) {
        if (shouldRetryWithApiProxyPrefix(path, error)) {
            try {
                return await performRequest(baseUrl, buildProxyCompatibleApiPath(path), {
                    token,
                    suppressSessionExpiryHandling,
                    ...rest,
                })
            } catch (retryError) {
                maybeHandleSessionExpiry(retryError, token, suppressSessionExpiryHandling)
                throw retryError
            }
        }

        maybeHandleSessionExpiry(error, token, suppressSessionExpiryHandling)
        throw error
    }
}

async function requestWithFallback(baseUrl, candidatePaths, options = {}, fallbackStatuses = [403, 404, 405]) {
    let lastError = null

    for (const candidatePath of candidatePaths) {
        try {
            return await request(baseUrl, candidatePath, options)
        } catch (error) {
            lastError = error
            const shouldTryNext =
                error instanceof BackendApiError &&
                (
                    fallbackStatuses.includes(Number(error.status)) ||
                    error?.details?.kind === 'unexpected_non_json'
                )

            if (!shouldTryNext) {
                throw error
            }
        }
    }

    throw lastError ?? new BackendApiError('Request failed.')
}

export async function loginForAccessToken(baseUrl, { username, password }) {
    const body = new URLSearchParams({
        username: String(username ?? ''),
        password: String(password ?? ''),
    })

    return normalizeTokenPayload(await requestWithFallback(baseUrl, ['/token', '/api/token'], {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body,
    }, [404, 405]))
}

export async function verifyPasswordForUser(baseUrl, {
    email,
    password,
    expectedUserId = null,
}) {
    const payload = await loginForAccessToken(baseUrl, {
        username: email,
        password,
    })

    const normalizedEmail = String(email || '').trim().toLowerCase()
    const responseEmail = String(payload?.email || '').trim().toLowerCase()
    if (normalizedEmail && responseEmail && normalizedEmail !== responseEmail) {
        throw new BackendApiError('Password confirmation matched a different account.')
    }

    const normalizedExpectedUserId = Number(expectedUserId)
    const responseUserId = Number(payload?.user_id)
    if (Number.isFinite(normalizedExpectedUserId) && Number.isFinite(responseUserId) && normalizedExpectedUserId !== responseUserId) {
        throw new BackendApiError('Password confirmation matched a different account.')
    }

    return true
}

export async function getDepartments(baseUrl, token = null) {
    const payload = await requestWithFallback(baseUrl, ['/api/departments/', '/departments/'], {
        method: 'GET',
        token,
    }, [404, 405])
    return Array.isArray(payload) ? payload.map(normalizeDepartment) : []
}

export async function createDepartment(baseUrl, token, payload) {
    return normalizeDepartment(await requestWithFallback(baseUrl, ['/api/departments/', '/departments/'], {
        method: 'POST',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }, [404, 405]))
}

export async function updateDepartment(baseUrl, token, departmentId, payload) {
    return normalizeDepartment(await requestWithFallback(baseUrl, [`/api/departments/${departmentId}`, `/departments/${departmentId}`], {
        method: 'PATCH',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }, [404, 405]))
}

export async function deleteDepartment(baseUrl, token, departmentId) {
    await requestWithFallback(baseUrl, [`/api/departments/${departmentId}`, `/departments/${departmentId}`], {
        method: 'DELETE',
        token,
    }, [404, 405])
    return true
}

export async function getPrograms(baseUrl, token = null) {
    const payload = await requestWithFallback(baseUrl, ['/api/programs/', '/programs/'], {
        method: 'GET',
        token,
    }, [404, 405])
    return Array.isArray(payload) ? payload.map(normalizeProgram) : []
}

export async function createProgram(baseUrl, token, payload) {
    return normalizeProgram(await requestWithFallback(baseUrl, ['/api/programs/', '/programs/'], {
        method: 'POST',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }, [404, 405]))
}

export async function updateProgram(baseUrl, token, programId, payload) {
    return normalizeProgram(await requestWithFallback(baseUrl, [`/api/programs/${programId}`, `/programs/${programId}`], {
        method: 'PATCH',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }, [404, 405]))
}

export async function deleteProgram(baseUrl, token, programId) {
    await requestWithFallback(baseUrl, [`/api/programs/${programId}`, `/programs/${programId}`], {
        method: 'DELETE',
        token,
    }, [404, 405])
    return true
}

export async function getSchoolSettings(baseUrl, token) {
    return normalizeSchoolSettings(await requestWithFallback(baseUrl, ['/api/school/me', '/api/school-settings/me', '/school-settings/me'], {
        method: 'GET',
        token,
    }, [404, 405]))
}

export async function updateSchoolSettings(baseUrl, token, payload) {
    return normalizeSchoolSettings(await requestWithFallback(baseUrl, ['/api/school-settings/me', '/school-settings/me'], {
        method: 'PUT',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }, [404, 405]))
}

export async function updateSchoolBranding(baseUrl, token, payload = {}, logoFile = null) {
    const formData = new FormData()

    if (payload.school_name !== undefined) {
        formData.append('school_name', String(payload.school_name ?? ''))
    }
    if (payload.primary_color !== undefined) {
        formData.append('primary_color', String(payload.primary_color ?? ''))
    }
    if (payload.secondary_color !== undefined) {
        formData.append('secondary_color', String(payload.secondary_color ?? ''))
    }
    if (payload.school_code !== undefined) {
        formData.append('school_code', String(payload.school_code ?? ''))
    }
    if (payload.event_default_early_check_in_minutes !== undefined) {
        formData.append('event_default_early_check_in_minutes', String(payload.event_default_early_check_in_minutes))
    }
    if (payload.event_default_late_threshold_minutes !== undefined) {
        formData.append('event_default_late_threshold_minutes', String(payload.event_default_late_threshold_minutes))
    }
    if (payload.event_default_sign_out_grace_minutes !== undefined) {
        formData.append('event_default_sign_out_grace_minutes', String(payload.event_default_sign_out_grace_minutes))
    }
    if (logoFile) {
        formData.append('logo', logoFile)
    }

    return normalizeSchoolSettings(await request(baseUrl, '/api/school/update', {
        method: 'PUT',
        token,
        body: formData,
    }))
}

export async function getEvents(baseUrl, token, params = {}) {
    const payload = await requestWithFallback(baseUrl, ['/api/events/', '/events/'], {
        method: 'GET',
        token,
        params,
    }, [404, 405])
    return Array.isArray(payload) ? payload.map(normalizeEvent) : []
}

export async function getEventById(baseUrl, token, eventId) {
    return normalizeEvent(await requestWithFallback(baseUrl, [`/api/events/${eventId}`, `/events/${eventId}`], {
        method: 'GET',
        token,
    }, [404, 405]))
}

export async function updateEvent(baseUrl, token, eventId, payload, params = {}) {
    return normalizeEvent(await requestWithFallback(baseUrl, [`/api/events/${eventId}`, `/events/${eventId}`], {
        method: 'PATCH',
        token,
        params,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }, [404, 405]))
}

export async function deleteEvent(baseUrl, token, eventId, params = {}) {
    await requestWithFallback(baseUrl, [`/api/events/${eventId}`, `/events/${eventId}`], {
        method: 'DELETE',
        token,
        params,
    }, [404, 405])
}

export async function getUsers(baseUrl, token, params = {}) {
    const payload = await requestWithFallback(baseUrl, ['/api/users/', '/users/'], {
        method: 'GET',
        token,
        params,
    }, [404, 405])
    return Array.isArray(payload) ? payload.map(normalizeUserWithRelations) : []
}

export async function getGovernanceAccess(baseUrl, token) {
    return request(baseUrl, '/api/governance/access/me', {
        method: 'GET',
        token,
    })
}

export async function getGovernanceUnitDetail(baseUrl, token, governanceUnitId) {
    return normalizeGovernanceUnitDetail(await request(baseUrl, `/api/governance/units/${governanceUnitId}`, {
        method: 'GET',
        token,
    }))
}

async function getGovernanceUnits(baseUrl, token) {
    const payload = await request(baseUrl, '/api/governance/units', {
        method: 'GET',
        token,
    })

    return Array.isArray(payload) ? payload.map(normalizeGovernanceUnitDetail) : []
}

function hasResolvedSsgUnit(setup = null) {
    return Number.isFinite(Number(setup?.unit?.id))
}

function pickSsgUnitFromGovernanceAccess(payload = null) {
    const units = Array.isArray(payload?.units) ? payload.units : []
    return units.find((unit) => String(unit?.unit_type || '').toUpperCase() === 'SSG') || null
}

function pickSsgUnitFromGovernanceUnits(units = [], schoolId = null) {
    const normalizedSchoolId = Number.isFinite(Number(schoolId)) ? Number(schoolId) : null
    const ssgUnits = (Array.isArray(units) ? units : [])
        .filter((unit) => String(unit?.unit_type || '').toUpperCase() === 'SSG')
        .filter((unit) => unit?.is_active !== false)
        .filter((unit) => (
            normalizedSchoolId == null
                ? true
                : Number(unit?.school_id) === normalizedSchoolId
        ))

    if (ssgUnits.length === 1) return ssgUnits[0]
    return null
}

export async function getCampusSsgSetup(baseUrl, token) {
    let primaryError = null

    try {
        const setup = normalizeGovernanceSsgSetup(await request(baseUrl, '/api/governance/ssg/setup', {
            method: 'GET',
            token,
        }))
        if (hasResolvedSsgUnit(setup)) {
            return setup
        }

        primaryError = new BackendApiError('Student Council setup returned an incomplete payload.', {
            details: setup,
        })
    } catch (error) {
        if (!(error instanceof BackendApiError)) {
            throw error
        }

        if (error.status === 403) {
            throw error
        }

        primaryError = error
    }

    let accessPayload = null
    try {
        accessPayload = await getGovernanceAccess(baseUrl, token)
        const accessUnit = pickSsgUnitFromGovernanceAccess(accessPayload)
        if (accessUnit?.governance_unit_id != null) {
            const detail = await getGovernanceUnitDetail(baseUrl, token, Number(accessUnit.governance_unit_id))
            const setup = normalizeGovernanceSsgSetup({
                unit: detail,
                total_imported_students: 0,
            })
            if (hasResolvedSsgUnit(setup)) {
                return setup
            }
        }
    } catch (error) {
        if (error instanceof BackendApiError && error.status === 403) {
            throw error
        }
    }

    try {
        const governanceUnits = await getGovernanceUnits(baseUrl, token)
        const fallbackUnit = pickSsgUnitFromGovernanceUnits(governanceUnits, accessPayload?.school_id)
        if (!fallbackUnit?.id) {
            if (primaryError?.status === 404) {
                return null
            }
            throw primaryError || new BackendApiError('Student Council setup could not be resolved from the backend.')
        }

        const detail = await getGovernanceUnitDetail(baseUrl, token, Number(fallbackUnit.id))
        const setup = normalizeGovernanceSsgSetup({
            unit: detail,
            total_imported_students: 0,
        })
        if (hasResolvedSsgUnit(setup)) {
            return setup
        }

        throw primaryError || new BackendApiError('Student Council setup could not be resolved from the backend.')
    } catch (error) {
        if (error instanceof BackendApiError && error.status === 403) {
            throw error
        }

        if (primaryError?.status === 404) {
            return null
        }

        throw primaryError || error
    }
}

export async function createGovernanceUnit(baseUrl, token, payload) {
    return normalizeGovernanceUnitDetail(await request(baseUrl, '/api/governance/units', {
        method: 'POST',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }))
}

export async function updateGovernanceUnit(baseUrl, token, governanceUnitId, payload) {
    return normalizeGovernanceUnitDetail(await request(baseUrl, `/api/governance/units/${governanceUnitId}`, {
        method: 'PATCH',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }))
}

export async function deleteGovernanceUnit(baseUrl, token, governanceUnitId) {
    await request(baseUrl, `/api/governance/units/${governanceUnitId}`, {
        method: 'DELETE',
        token,
    })
    return true
}

export async function searchGovernanceStudentCandidates(baseUrl, token, params = {}) {
    const payload = await request(baseUrl, '/api/governance/students/search', {
        method: 'GET',
        token,
        params,
    })
    return Array.isArray(payload) ? payload.map(normalizeGovernanceStudentCandidate) : []
}

export async function assignGovernanceMember(baseUrl, token, governanceUnitId, payload) {
    return normalizeGovernanceMember(await request(baseUrl, `/api/governance/units/${governanceUnitId}/members`, {
        method: 'POST',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }))
}

export async function updateGovernanceMember(baseUrl, token, governanceMemberId, payload) {
    return normalizeGovernanceMember(await request(baseUrl, `/api/governance/members/${governanceMemberId}`, {
        method: 'PATCH',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }))
}

export async function deleteGovernanceMember(baseUrl, token, governanceMemberId) {
    await request(baseUrl, `/api/governance/members/${governanceMemberId}`, {
        method: 'DELETE',
        token,
    })
    return true
}

export async function getGovernanceStudents(baseUrl, token, params = {}) {
    const payload = await request(baseUrl, '/api/governance/students', {
        method: 'GET',
        token,
        params,
    })
    return Array.isArray(payload) ? payload : []
}

export async function getGovernanceAnnouncements(baseUrl, token, governanceUnitId) {
    const payload = await request(baseUrl, `/api/governance/units/${governanceUnitId}/announcements`, {
        method: 'GET',
        token,
    })
    return Array.isArray(payload) ? payload : []
}

export async function createGovernanceAnnouncement(baseUrl, token, governanceUnitId, payload) {
    return request(baseUrl, `/api/governance/units/${governanceUnitId}/announcements`, {
        method: 'POST',
        token,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    })
}

export async function updateGovernanceAnnouncement(baseUrl, token, announcementId, payload) {
    return request(baseUrl, `/api/governance/announcements/${announcementId}`, {
        method: 'PATCH',
        token,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    })
}

export async function deleteGovernanceAnnouncement(baseUrl, token, announcementId) {
    await request(baseUrl, `/api/governance/announcements/${announcementId}`, {
        method: 'DELETE',
        token,
    })
    return true
}

export async function createSchoolWithSchoolIt(baseUrl, token, payload) {
    const formData = new FormData()

    appendFormValue(formData, 'school_name', payload.school_name)
    appendFormValue(formData, 'primary_color', payload.primary_color)
    appendFormValue(formData, 'secondary_color', payload.secondary_color)
    appendFormValue(formData, 'school_code', payload.school_code)
    appendFormValue(formData, 'school_it_email', payload.school_it_email)
    appendFormValue(formData, 'school_it_first_name', payload.school_it_first_name)
    appendFormValue(formData, 'school_it_middle_name', payload.school_it_middle_name)
    appendFormValue(formData, 'school_it_last_name', payload.school_it_last_name)
    appendFormValue(formData, 'school_it_password', payload.school_it_password)

    if (payload.logo) {
        formData.append('logo', payload.logo, payload.logo_name || 'logo.png')
    }

    return normalizeCreateSchoolWithSchoolItResponse(await request(baseUrl, '/api/school/admin/create-school-it', {
        method: 'POST',
        token,
        body: formData,
    }))
}

export async function getAdminSchools(baseUrl, token) {
    const payload = await request(baseUrl, '/api/school/admin/list', {
        method: 'GET',
        token,
    })

    return Array.isArray(payload) ? payload.map(normalizeSchoolSummary).filter(Boolean) : []
}

export async function updateAdminSchoolStatus(baseUrl, token, schoolId, payload) {
    return normalizeSchoolSettings(await request(baseUrl, `/api/school/admin/${schoolId}/status`, {
        method: 'PATCH',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }))
}

export async function getAdminSchoolItAccounts(baseUrl, token) {
    const payload = await request(baseUrl, '/api/school/admin/school-it-accounts', {
        method: 'GET',
        token,
    })

    return Array.isArray(payload) ? payload.map(normalizeSchoolItAccount).filter(Boolean) : []
}

export async function updateAdminSchoolItAccountStatus(baseUrl, token, userId, isActive) {
    return normalizeSchoolItAccount(await request(baseUrl, `/api/school/admin/school-it-accounts/${userId}/status`, {
        method: 'PATCH',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            is_active: Boolean(isActive),
        }),
    }))
}

export async function resetAdminSchoolItPassword(baseUrl, token, userId) {
    return normalizePasswordResetResponse(await request(baseUrl, `/api/school/admin/school-it-accounts/${userId}/reset-password`, {
        method: 'POST',
        token,
    }))
}

export async function getAuditLogs(baseUrl, token, params = {}) {
    return normalizeAuditLogResponse(await request(baseUrl, '/api/audit-logs', {
        method: 'GET',
        token,
        params,
    }))
}

export async function getNotificationLogs(baseUrl, token, params = {}) {
    const payload = await request(baseUrl, '/api/notifications/logs', {
        method: 'GET',
        token,
        params,
    })

    return Array.isArray(payload) ? payload.map(normalizeNotificationLogItem).filter(Boolean) : []
}

export async function dispatchMissedEventNotifications(baseUrl, token, params = {}) {
    return normalizeNotificationDispatchSummary(await request(baseUrl, '/api/notifications/dispatch/missed-events', {
        method: 'POST',
        token,
        params,
    }))
}

export async function dispatchLowAttendanceNotifications(baseUrl, token, params = {}) {
    return normalizeNotificationDispatchSummary(await request(baseUrl, '/api/notifications/dispatch/low-attendance', {
        method: 'POST',
        token,
        params,
    }))
}

export async function getGovernanceSettings(baseUrl, token, params = {}) {
    return normalizeGovernanceSetting(await request(baseUrl, '/api/governance/settings/me', {
        method: 'GET',
        token,
        params,
    }))
}

export async function updateGovernanceSettings(baseUrl, token, payload, params = {}) {
    return normalizeGovernanceSetting(await request(baseUrl, '/api/governance/settings/me', {
        method: 'PUT',
        token,
        params,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }))
}

export async function getGovernanceRequests(baseUrl, token, params = {}) {
    const payload = await request(baseUrl, '/api/governance/requests', {
        method: 'GET',
        token,
        params,
    })

    return Array.isArray(payload) ? payload.map(normalizeGovernanceRequest).filter(Boolean) : []
}

export async function updateGovernanceRequest(baseUrl, token, requestId, payload) {
    return normalizeGovernanceRequest(await request(baseUrl, `/api/governance/requests/${requestId}`, {
        method: 'PATCH',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }))
}

export async function runGovernanceRetention(baseUrl, token, payload, params = {}) {
    return normalizeRetentionRunResult(await request(baseUrl, '/api/governance/run-retention', {
        method: 'POST',
        token,
        params,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }))
}

export async function createUser(baseUrl, token, payload) {
    return normalizeUserCreateResponse(await requestWithFallback(baseUrl, ['/api/users/', '/users/'], {
        method: 'POST',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }, [404, 405]))
}

export async function createStudentAccount(baseUrl, token, payload) {
    return normalizeUserWithRelations(await requestWithFallback(baseUrl, ['/api/users/students/', '/users/students/'], {
        method: 'POST',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }, [404, 405]))
}

export async function createStudentProfile(baseUrl, token, payload) {
    return normalizeUserWithRelations(await requestWithFallback(baseUrl, ['/api/users/admin/students/', '/users/admin/students/'], {
        method: 'POST',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }, [404, 405]))
}

export async function previewImportStudents(baseUrl, token, file) {
    const formData = new FormData()
    formData.append('file', file)

    return normalizeImportPreviewSummary(await request(baseUrl, '/api/admin/import-students/preview', {
        method: 'POST',
        token,
        body: formData,
    }))
}

export async function startStudentImport(baseUrl, token, previewToken) {
    const formData = new FormData()
    formData.append('preview_token', String(previewToken || ''))

    return normalizeImportJobCreateResponse(await request(baseUrl, '/api/admin/import-students', {
        method: 'POST',
        token,
        body: formData,
    }))
}

export async function getStudentImportStatus(baseUrl, token, jobId) {
    return normalizeImportJobStatus(await request(baseUrl, `/api/admin/import-status/${jobId}`, {
        method: 'GET',
        token,
    }))
}

async function downloadBinary(baseUrl, path, { token, params } = {}) {
    const timeoutMs = resolveApiTimeoutMs()
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

    try {
        const response = await fetch(buildUrl(baseUrl, path, params), {
            method: 'GET',
            signal: controller.signal,
            headers: {
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
                ...(isNgrokApiBaseUrl(baseUrl) ? { 'ngrok-skip-browser-warning': 'true' } : {}),
            },
        })

        if (!response.ok) {
            const contentType = response.headers.get('content-type') || ''
            const isJson = contentType.includes('application/json')
            let payload = null

            try {
                payload = isJson ? await response.json() : await response.text()
            } catch {
                payload = null
            }

            const message =
                payload?.detail?.message ||
                payload?.detail ||
                payload?.message ||
                response.statusText ||
                'Request failed.'

            throw new BackendApiError(String(message), {
                status: response.status,
                details: payload,
            })
        }

        return await response.blob()
    } catch (error) {
        if (error?.name === 'AbortError') {
            throw new BackendApiError(
                `The API took too long to respond. The backend may be offline. (${timeoutMs}ms timeout)`,
                {
                    details: {
                        path,
                        timeoutMs,
                    },
                }
            )
        }

        if (error instanceof BackendApiError) {
            throw error
        }

        throw new BackendApiError(
            'Unable to reach the API. The server may be unavailable or the request may be blocked.',
            {
                details: {
                    cause: error?.message || null,
                    path,
                },
            }
        )
    } finally {
        clearTimeout(timeoutId)
    }
}

export async function downloadStudentImportTemplate(baseUrl, token) {
    return downloadBinary(baseUrl, '/api/admin/import-students/template', {
        token,
    })
}

export async function downloadPreviewImportErrors(baseUrl, token, previewToken) {
    return downloadBinary(baseUrl, `/api/admin/import-preview-errors/${previewToken}/download`, {
        token,
    })
}

export async function downloadPreviewRetryFile(baseUrl, token, previewToken) {
    return downloadBinary(baseUrl, `/api/admin/import-preview-errors/${previewToken}/retry-download`, {
        token,
    })
}

export async function removeInvalidPreviewRows(baseUrl, token, previewToken) {
    return normalizeImportPreviewSummary(await request(baseUrl, `/api/admin/import-preview-errors/${previewToken}/remove-invalid`, {
        method: 'POST',
        token,
    }))
}

export async function downloadImportErrors(baseUrl, token, jobId) {
    return downloadBinary(baseUrl, `/api/admin/import-errors/${jobId}/download`, {
        token,
    })
}

export async function getCurrentUserProfile(baseUrl, token) {
    const payload = await requestWithFallback(baseUrl, ['/api/users/me/', '/users/me/'], {
        method: 'GET',
        token,
    }, [404, 405])
    const normalized = normalizeUserWithRelations(payload)
    if (!normalized) {
        throw new BackendApiError('The API returned an invalid current-user profile response.', {
            details: payload,
        })
    }
    return normalized
}

export async function getUserById(baseUrl, token, userId) {
    return normalizeUserWithRelations(await requestWithFallback(baseUrl, [`/api/users/${userId}`, `/users/${userId}`], {
        method: 'GET',
        token,
    }, [404, 405]))
}

export async function updateUser(baseUrl, token, userId, payload) {
    return normalizeUserWithRelations(await requestWithFallback(baseUrl, [`/api/users/${userId}`, `/users/${userId}`], {
        method: 'PATCH',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }, [404, 405]))
}

export async function updateStudentProfile(baseUrl, token, profileId, payload) {
    return normalizeUserWithRelations(await requestWithFallback(baseUrl, [`/api/users/student-profiles/${profileId}`, `/users/student-profiles/${profileId}`], {
        method: 'PATCH',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }, [404, 405]))
}

export async function deleteUser(baseUrl, token, userId) {
    await requestWithFallback(baseUrl, [`/api/users/${userId}`, `/users/${userId}`], {
        method: 'DELETE',
        token,
    }, [404, 405])
}

export async function resetUserPassword(baseUrl, token, userId, password) {
    return normalizePasswordResetResponse(await requestWithFallback(baseUrl, [`/api/users/${userId}/reset-password`, `/users/${userId}/reset-password`], {
        method: 'POST',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            password,
        }),
    }, [404, 405]))
}

export async function changePassword(baseUrl, token, payload, endpoint = '/auth/change-password') {
    return normalizePasswordChangeResponse(await request(baseUrl, endpoint, {
        method: 'POST',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }))
}

function normalizeStudentAttendanceResponsePayload(payload = []) {
    if (!Array.isArray(payload)) return []

    return payload.flatMap((item) => {
        const studentAttendances = Array.isArray(item?.attendances) ? item.attendances : []
        const responseStudentId = item?.student_id ?? null

        return studentAttendances.map((attendance) => normalizeAttendanceRecord({
            ...attendance,
            student_id: attendance?.student_id ?? responseStudentId,
        }))
    })
}

function normalizeAttendanceCollectionPayload(payload = null) {
    if (!Array.isArray(payload)) return []

    const looksNestedStudentResponse = payload.some((item) => Array.isArray(item?.attendances))
    if (looksNestedStudentResponse) {
        return normalizeStudentAttendanceResponsePayload(payload)
    }

    return payload.map(normalizeAttendanceRecord)
}

export async function getMyAttendance(baseUrl, token, params = {}) {
    const payload = await requestWithFallback(baseUrl, [
        '/api/attendance/me/records',
        '/attendance/me/records',
        '/api/attendance/students/me',
        '/attendance/students/me',
    ], {
        method: 'GET',
        token,
        params,
    }, [403, 404, 405])
    return normalizeAttendanceCollectionPayload(payload)
}

export async function createAnnouncement(baseUrl, token, payload) {
    return requestWithFallback(baseUrl, ['/api/announcements', '/announcements'], {
        method: 'POST',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }, [404, 405])
}

/**
 * Creates a new governance event
 * @param {string} baseUrl - Base URL of the API
 * @param {string} token - Session token
 * @param {Object} payload - Event data payload
 * @returns {Promise<Object>} The created event
 */
export async function createGovernanceEvent(baseUrl, token, payload, params = {}) {
    return normalizeEvent(await requestWithFallback(baseUrl, ['/api/events/', '/events/', '/api/governance/events'], {
        method: 'POST',
        token,
        params,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }, [404, 405]))
}

export async function getAttendanceSummary(baseUrl, token, params = {}) {
    return request(baseUrl, '/attendance/summary', {
        method: 'GET',
        token,
        params,
    })
}

export async function getEventAttendance(baseUrl, token, eventId, params = {}) {
    const payload = await requestWithFallback(baseUrl, [
        `/api/attendance/events/${eventId}/attendances-with-students`,
        `/api/attendance/events/${eventId}/attendances`,
        `/attendance/events/${eventId}/attendances-with-students`,
        `/attendance/events/${eventId}/attendances`,
    ], {
        method: 'GET',
        token,
        params: {
            active_only: false,
            ...params,
        },
    }, [404, 405])
    return Array.isArray(payload) ? payload.map(normalizeEventAttendanceWithStudent) : []
}

export async function getEventAttendanceReport(baseUrl, token, eventId, params = {}) {
    return normalizeEventAttendanceReport(await requestWithFallback(baseUrl, [
        `/api/attendance/events/${eventId}/report`,
        `/attendance/events/${eventId}/report`,
    ], {
        method: 'GET',
        token,
        params,
    }, [404, 405]))
}

export async function getFaceStatus(baseUrl, token) {
    return normalizeFaceStatus(await requestWithFallback(baseUrl, ['/api/auth/security/face-status', '/auth/security/face-status'], {
        method: 'GET',
        token,
    }, [404, 405]))
}

export async function saveFaceReference(baseUrl, token, imageBase64) {
    return normalizeFaceReferenceResponse(await requestWithFallback(baseUrl, ['/api/auth/security/face-reference', '/auth/security/face-reference'], {
        method: 'POST',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            image_base64: imageBase64,
        }),
    }, [404, 405]))
}

export async function registerStudentFace(baseUrl, token, imageBase64) {
    return normalizeStudentFaceRegistrationResponse(await requestWithFallback(baseUrl, ['/api/face/register', '/face/register'], {
        method: 'POST',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            image_base64: imageBase64,
        }),
    }))
}

export async function verifyFaceReference(baseUrl, token, payload) {
    return normalizeFaceVerificationResponse(await requestWithFallback(baseUrl, ['/api/auth/security/face-verify', '/auth/security/face-verify'], {
        method: 'POST',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }, [404, 405]))
}

export async function recordFaceScanAttendance(baseUrl, token, {
    eventId,
    studentId,
    imageBase64,
    latitude = null,
    longitude = null,
    accuracyM = null,
    threshold = null,
}) {
    const payload = await requestWithFallback(baseUrl, ['/api/face/face-scan-with-recognition', '/face/face-scan-with-recognition'], {
        method: 'POST',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            event_id: eventId,
            image_base64: imageBase64,
            latitude,
            longitude,
            accuracy_m: accuracyM,
            threshold,
        }),
    })
    return {
        ok: payload?.ok !== false,
        ...payload,
        geo: payload?.geo ? normalizeEventLocationResponse(payload.geo) : null,
    }
}

export async function recordFaceScanTimeout(baseUrl, token, { eventId, studentId }) {
    const payload = await requestWithFallback(baseUrl, ['/api/attendance/face-scan-timeout', '/attendance/face-scan-timeout'], {
        method: 'POST',
        token,
        params: {
            event_id: eventId,
            student_id: studentId,
        },
    })
    return { ok: payload?.ok !== false, ...payload }
}

export async function verifyEventLocation(baseUrl, token, eventId, payload) {
    return normalizeEventLocationResponse(await requestWithFallback(baseUrl, [`/api/events/${eventId}/verify-location`, `/events/${eventId}/verify-location`], {
        method: 'POST',
        token,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    }))
}

export async function getEventTimeStatus(baseUrl, token, eventId) {
    return normalizeEventTimeStatus(await requestWithFallback(baseUrl, [`/api/events/${eventId}/time-status`, `/events/${eventId}/time-status`], {
        method: 'GET',
        token,
    }))
}

function appendFormValue(formData, key, value) {
    if (value == null || value === '') return
    formData.append(key, String(value))
}
