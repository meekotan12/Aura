import { computed, reactive, readonly } from 'vue'
import { applyTheme, loadTheme } from '@/config/theme.js'
import {
    getFaceStatus,
    getCurrentUserProfile,
    getEventById,
    getEvents,
    getMyAttendance,
    getSchoolSettings,
    resolveApiBaseUrl,
    updateUser,
} from '@/services/backendApi.js'
import {
    isOpenAttendanceRecord,
    isResolvedAttendanceRecord,
} from '@/services/attendanceFlow.js'
import { resolveBackendMediaUrl } from '@/services/backendMedia.js'
import { clearStoredAuthMeta, getStoredAuthMeta, patchStoredAuthMeta } from '@/services/localAuth.js'

const DASHBOARD_CACHE_KEY = 'aura_dashboard_cache_v1'
const DEFAULT_CACHE_TTL_MS = 5 * 60 * 1000
const configuredCacheTtl = Number(import.meta.env.VITE_DASHBOARD_CACHE_TTL_MS)
const DASHBOARD_CACHE_TTL_MS = Number.isFinite(configuredCacheTtl) && configuredCacheTtl > 0
    ? configuredCacheTtl
    : DEFAULT_CACHE_TTL_MS

const state = reactive({
    apiBaseUrl: resolveApiBaseUrl(),
    token: localStorage.getItem('aura_token') || '',
    initializedToken: '',
    user: null,
    schoolSettings: null,
    events: [],
    attendanceRecords: [],
    faceStatus: null,
    initialized: false,
    loading: false,
    limitedMode: false,
    error: '',
})

let initPromise = null

function buildCacheIdentity(token = state.token, authMeta = getStoredAuthMeta()) {
    const normalizedToken = String(token || '').trim()
    return {
        tokenSuffix: normalizedToken ? normalizedToken.slice(-24) : null,
        sessionId: authMeta?.sessionId || null,
        userId: Number.isFinite(Number(authMeta?.userId)) ? Number(authMeta.userId) : null,
        email: authMeta?.email || null,
        schoolId: Number.isFinite(Number(authMeta?.schoolId)) ? Number(authMeta.schoolId) : null,
    }
}

function readDashboardCache() {
    try {
        const raw = localStorage.getItem(DASHBOARD_CACHE_KEY)
        if (!raw) return null
        return JSON.parse(raw)
    } catch {
        localStorage.removeItem(DASHBOARD_CACHE_KEY)
        return null
    }
}

function isMatchingCacheIdentity(identity, expected) {
    if (!identity || !expected) return false

    const comparableKeys = ['tokenSuffix', 'sessionId', 'userId', 'email', 'schoolId']
    return comparableKeys.every((key) => {
        const expectedValue = expected[key]
        if (expectedValue == null || expectedValue === '') return true
        return identity[key] === expectedValue
    })
}

function isCacheFresh(savedAt) {
    const savedTime = Number(savedAt)
    if (!Number.isFinite(savedTime)) return false
    return Date.now() - savedTime <= DASHBOARD_CACHE_TTL_MS
}

function persistDashboardSnapshot() {
    if (!state.token || !state.user || state.limitedMode) {
        clearDashboardSnapshot()
        return
    }

    const authMeta = getStoredAuthMeta()
    const payload = {
        version: 1,
        savedAt: Date.now(),
        identity: buildCacheIdentity(state.token, authMeta),
        snapshot: {
            user: state.user,
            schoolSettings: state.schoolSettings,
            events: state.events,
            attendanceRecords: state.attendanceRecords,
            faceStatus: state.faceStatus,
            limitedMode: false,
        },
    }

    localStorage.setItem(DASHBOARD_CACHE_KEY, JSON.stringify(payload))

    if (state.schoolSettings) {
        patchStoredAuthMeta({
            schoolId: state.schoolSettings.school_id ?? authMeta?.schoolId ?? null,
            schoolName: state.schoolSettings.school_name ?? authMeta?.schoolName ?? null,
            schoolCode: state.schoolSettings.school_code ?? authMeta?.schoolCode ?? null,
            logoUrl: state.schoolSettings.logo_url ?? authMeta?.logoUrl ?? null,
            primaryColor: state.schoolSettings.primary_color ?? authMeta?.primaryColor ?? null,
            secondaryColor: state.schoolSettings.secondary_color ?? authMeta?.secondaryColor ?? null,
            accentColor: state.schoolSettings.accent_color ?? authMeta?.accentColor ?? null,
        })
    }
}

function clearDashboardSnapshot() {
    localStorage.removeItem(DASHBOARD_CACHE_KEY)
}

function applyDashboardSnapshot(snapshot, token = state.token) {
    if (!snapshot) return false

    state.user = snapshot.user ?? null
    state.schoolSettings = snapshot.schoolSettings ?? null
    state.events = Array.isArray(snapshot.events) ? sortEvents(snapshot.events.map(normalizeEvent).filter(Boolean)) : []
    state.attendanceRecords = Array.isArray(snapshot.attendanceRecords) ? snapshot.attendanceRecords : []
    state.faceStatus = snapshot.faceStatus ?? null
    state.limitedMode = Boolean(snapshot.limitedMode)
    state.initialized = true
    state.initializedToken = String(token || '')
    state.loading = false
    state.error = ''
    syncUserAttendanceRecords()
    syncUserFaceState()
    applyActiveTheme()
    return true
}

function hydrateDashboardStateFromCache(token = state.token, authMeta = getStoredAuthMeta()) {
    const cached = readDashboardCache()
    if (!cached?.snapshot || !isMatchingCacheIdentity(cached.identity, buildCacheIdentity(token, authMeta))) {
        return { hydrated: false, stale: true }
    }

    const hydrated = applyDashboardSnapshot(cached.snapshot, token)
    return {
        hydrated,
        stale: !isCacheFresh(cached.savedAt),
    }
}

function normalizeEvent(event) {
    if (!event) return null

    const status = event.status === 'done' ? 'completed' : event.status
    return {
        ...event,
        status,
    }
}

function sortEvents(events) {
    const statusRank = {
        ongoing: 0,
        upcoming: 1,
        completed: 2,
        cancelled: 3,
    }

    return [...events].sort((a, b) => {
        const aRank = statusRank[a?.status] ?? 99
        const bRank = statusRank[b?.status] ?? 99
        if (aRank !== bRank) return aRank - bRank
        return new Date(a?.start_datetime ?? 0) - new Date(b?.start_datetime ?? 0)
    })
}

function syncUserAttendanceRecords() {
    if (!state.user?.student_profile) return

    state.user = {
        ...state.user,
        student_profile: {
            ...state.user.student_profile,
            attendances: [...state.attendanceRecords],
        },
    }
}

function resolveStudentFaceRegistered(user = state.user, authMeta = getStoredAuthMeta(), faceStatus = state.faceStatus) {
    if (!user?.student_profile) {
        return Boolean(
            faceStatus?.face_reference_enrolled ??
            authMeta?.faceReferenceEnrolled
        )
    }

    return Boolean(
        faceStatus?.face_reference_enrolled ||
        user.student_profile?.is_face_registered ||
        user.student_profile?.registration_complete ||
        authMeta?.faceReferenceEnrolled
    )
}

function syncUserFaceState() {
    if (!state.user?.student_profile) return

    const isFaceRegistered = resolveStudentFaceRegistered(state.user)

    state.user = {
        ...state.user,
        student_profile: {
            ...state.user.student_profile,
            is_face_registered: isFaceRegistered,
            registration_complete: isFaceRegistered || Boolean(state.user.student_profile?.registration_complete),
        },
    }
}

function getRoleNames(user) {
    if (!Array.isArray(user?.roles)) return []

    return user.roles
        .map((entry) => entry?.role?.name || entry?.name || entry)
        .filter(Boolean)
        .map((role) => String(role))
}

function normalizeRoleKey(role) {
    const normalized = String(role || '').trim().toLowerCase().replace(/_/g, '-')
    if (normalized === 'campus-admin') return 'school-it'
    return normalized
}

function hasRole(user, roleName) {
    const normalizedExpected = normalizeRoleKey(roleName)
    return getRoleNames(user).some(
        (role) => normalizeRoleKey(role) === normalizedExpected
    )
}

function isPrivilegedFaceUser(user) {
    return hasRole(user, 'admin') || hasRole(user, 'school_IT')
}

function isSchoolItUser(user) {
    return hasRole(user, 'school_IT')
}

function isAdminUser(user) {
    return hasRole(user, 'admin') && !isSchoolItUser(user)
}

function applyActiveTheme() {
    applyTheme(loadTheme(
        state.schoolSettings
        || buildFallbackSchoolSettings(getStoredAuthMeta())
    ))
}

function resetDashboardState() {
    state.user = null
    state.schoolSettings = null
    state.events = []
    state.attendanceRecords = []
    state.faceStatus = null
    state.initialized = false
    state.initializedToken = ''
    state.loading = false
    state.limitedMode = false
    state.error = ''
    applyActiveTheme()
}

function buildFallbackUserFromAuthMeta(authMeta = getStoredAuthMeta()) {
    if (!authMeta?.email) return null

    const roleNames = Array.isArray(authMeta.roles) ? authMeta.roles.filter(Boolean) : []
    const roleRelations = roleNames.map((roleName, index) => ({
        id: index + 1,
        role: {
            id: index + 1,
            name: roleName,
        },
    }))

    const normalizedRoles = roleNames
        .map((roleName) => String(roleName).trim().toLowerCase().replace(/_/g, '-'))
    const isStudent = normalizedRoles.includes('student')

    return {
        id: authMeta.userId ?? 0,
        email: authMeta.email,
        first_name: authMeta.firstName || authMeta.email.split('@')[0] || 'Student',
        middle_name: null,
        last_name: authMeta.lastName || '',
        is_active: true,
        created_at: new Date().toISOString(),
        school_id: authMeta.schoolId ?? null,
        school_name: authMeta.schoolName ?? null,
        school_code: authMeta.schoolCode ?? null,
        roles: roleRelations,
        student_profile: isStudent
            ? {
                id: null,
                user_id: authMeta.userId ?? 0,
                school_id: authMeta.schoolId ?? null,
                student_id: null,
                department_id: null,
                program_id: null,
                year_level: null,
                attendances: [],
                is_face_registered: Boolean(authMeta.faceReferenceEnrolled),
                registration_complete: Boolean(authMeta.faceReferenceEnrolled),
                photo_url: null,
                avatar_url: null,
            }
            : null,
        avatar_url: null,
        must_change_password: Boolean(authMeta.mustChangePassword),
    }
}

function buildFallbackSchoolSettings(authMeta = getStoredAuthMeta()) {
    if (!authMeta?.schoolId) return null

    return {
        school_id: authMeta.schoolId,
        school_name: authMeta.schoolName || 'School',
        school_code: authMeta.schoolCode || null,
        logo_url: resolveBackendMediaUrl(authMeta.logoUrl || null),
        primary_color: authMeta.primaryColor || loadTheme().primaryColor,
        secondary_color: authMeta.secondaryColor || loadTheme().primaryDark,
        accent_color: authMeta.accentColor || '#000000',
        subscription_status: 'trial',
        active_status: true,
    }
}

function setToken(token) {
    state.token = String(token || '')
    if (state.token) {
        localStorage.setItem('aura_token', state.token)
    } else {
        localStorage.removeItem('aura_token')
    }
}

async function fetchDashboardData() {
    if (!state.token) {
        resetDashboardState()
        return null
    }

    state.loading = true
    state.error = ''
    const authMeta = getStoredAuthMeta()

    try {
        let user = null
        let usingFallbackUser = false

        try {
            user = await getCurrentUserProfile(state.apiBaseUrl, state.token)
        } catch (error) {
            user = buildFallbackUserFromAuthMeta(authMeta)
            usingFallbackUser = Boolean(user)
            if (!user) {
                throw error
            }
        }

        const shouldLoadPrivilegedFaceStatus = isPrivilegedFaceUser(user)

        const [settingsResult, eventsResult, attendanceResult, faceStatusResult] = await Promise.allSettled([
            getSchoolSettings(state.apiBaseUrl, state.token),
            getEvents(state.apiBaseUrl, state.token, { limit: 200 }),
            getMyAttendance(state.apiBaseUrl, state.token, { limit: 200 }),
            shouldLoadPrivilegedFaceStatus
                ? getFaceStatus(state.apiBaseUrl, state.token)
                : Promise.resolve(null),
        ])

        const schoolId = Number(user?.school_id)
        const nextEvents = eventsResult.status === 'fulfilled' && Array.isArray(eventsResult.value)
            ? eventsResult.value
                .map(normalizeEvent)
                .filter(Boolean)
                .filter((event) => !Number.isFinite(schoolId) || Number(event?.school_id) === schoolId)
            : []

        state.user = user
        state.schoolSettings = settingsResult.status === 'fulfilled'
            ? settingsResult.value
            : buildFallbackSchoolSettings(authMeta)
        state.events = sortEvents(nextEvents)
        state.attendanceRecords = attendanceResult.status === 'fulfilled' && Array.isArray(attendanceResult.value)
            ? attendanceResult.value
            : []
        state.faceStatus = faceStatusResult.status === 'fulfilled' && faceStatusResult.value
            ? faceStatusResult.value
            : {
                face_reference_enrolled: resolveStudentFaceRegistered(user, authMeta, null),
            }
        state.limitedMode = usingFallbackUser
        state.initialized = true
        state.initializedToken = state.token
        syncUserAttendanceRecords()
        syncUserFaceState()
        applyActiveTheme()
        persistDashboardSnapshot()
        if (usingFallbackUser) {
            state.error = 'Some backend profile endpoints are failing, so Aura is using a limited session fallback.'
        }

        return state
    } catch (error) {
        const fallbackUser = buildFallbackUserFromAuthMeta(authMeta)

        if (fallbackUser) {
            state.user = fallbackUser
            state.schoolSettings = buildFallbackSchoolSettings(authMeta)
            state.events = []
            state.attendanceRecords = []
            state.faceStatus = {
                face_reference_enrolled: resolveStudentFaceRegistered(fallbackUser, authMeta, null),
            }
            state.limitedMode = true
            state.initialized = true
            state.initializedToken = state.token
            syncUserAttendanceRecords()
            syncUserFaceState()
            applyActiveTheme()
            persistDashboardSnapshot()
            state.error = 'Some backend endpoints are failing, so Aura is using a limited fallback session.'
            return state
        }

        state.error = error?.message || 'Unable to load dashboard data.'
        throw error
    } finally {
        state.loading = false
    }
}

export function hasSessionToken() {
    return Boolean(localStorage.getItem('aura_token'))
}

export async function initializeDashboardSession(force = false) {
    const resolvedApiBaseUrl = resolveApiBaseUrl()
    const storedToken = localStorage.getItem('aura_token') || ''

    state.apiBaseUrl = resolvedApiBaseUrl
    state.token = storedToken

    if (!state.token) {
        resetDashboardState()
        return null
    }

    if (Boolean(getStoredAuthMeta()?.mustChangePassword)) {
        resetDashboardState()
        return null
    }

    if (initPromise && !force) {
        return initPromise
    }

    if (!force && state.initialized && state.initializedToken === storedToken) {
        return state
    }

    if (!force && !state.initialized) {
        const cachedState = hydrateDashboardStateFromCache(storedToken)
        if (cachedState.hydrated) {
            if (!cachedState.stale) {
                return state
            }

            if (!initPromise) {
                initPromise = fetchDashboardData().finally(() => {
                    initPromise = null
                })
            }

            return state
        }
    }

    initPromise = fetchDashboardData().finally(() => {
        initPromise = null
    })

    return initPromise
}

export async function refreshAttendanceRecords(params = {}) {
    if (!state.token) return []

    const records = await getMyAttendance(state.apiBaseUrl, state.token, {
        limit: 200,
        ...params,
    })

    const freshRecords = Array.isArray(records) ? records : []

    if (params.event_id != null) {
        const filteredEventId = Number(params.event_id)
        const kept = state.attendanceRecords.filter(
            (r) => Number(r?.event_id) !== filteredEventId
        )
        state.attendanceRecords = [...kept, ...freshRecords]
    } else {
        state.attendanceRecords = freshRecords
    }

    syncUserAttendanceRecords()
    persistDashboardSnapshot()
    return state.attendanceRecords
}

export function replaceAttendanceRecordsForEvent(eventId, records = []) {
    const normalizedEventId = Number(eventId)
    if (!Number.isFinite(normalizedEventId)) {
        return state.attendanceRecords
    }

    const nextRecords = Array.isArray(records)
        ? records.filter((record) => Number(record?.event_id) === normalizedEventId)
        : []

    const keptRecords = state.attendanceRecords.filter(
        (record) => Number(record?.event_id) !== normalizedEventId
    )

    state.attendanceRecords = [...keptRecords, ...nextRecords]
    syncUserAttendanceRecords()
    persistDashboardSnapshot()
    return state.attendanceRecords
}

export function upsertAttendanceRecordSnapshot(record) {
    if (!record || typeof record !== 'object') {
        return state.attendanceRecords
    }

    const normalizedEventId = Number(record.event_id)
    if (!Number.isFinite(normalizedEventId)) {
        return state.attendanceRecords
    }

    return replaceAttendanceRecordsForEvent(normalizedEventId, [record])
}

export async function refreshSchoolSettings() {
    if (!state.token) return null

    const nextSchoolSettings = await getSchoolSettings(state.apiBaseUrl, state.token)
    applySchoolSettingsSnapshot(nextSchoolSettings)
    return state.schoolSettings
}

export async function refreshFaceStatus() {
    if (!state.token) return null

    if (!isPrivilegedFaceUser(state.user)) {
        const fallbackUser = buildFallbackUserFromAuthMeta()
        const user = await getCurrentUserProfile(state.apiBaseUrl, state.token).catch(() => fallbackUser)
        if (!user) return null
        state.user = user
        state.faceStatus = {
            face_reference_enrolled: resolveStudentFaceRegistered(user, getStoredAuthMeta(), null),
        }
        syncUserFaceState()
        persistDashboardSnapshot()
        return state.faceStatus
    }

    const nextFaceStatus = await getFaceStatus(state.apiBaseUrl, state.token)
    state.faceStatus = nextFaceStatus
    syncUserFaceState()
    persistDashboardSnapshot()
    return state.faceStatus
}

export async function ensureDashboardEvent(eventId) {
    const normalizedEventId = Number(eventId)
    if (!Number.isFinite(normalizedEventId) || !state.token) return null

    const existing = state.events.find((event) => Number(event?.id) === normalizedEventId)
    if (existing) return existing

    const event = normalizeEvent(await getEventById(state.apiBaseUrl, state.token, normalizedEventId))
    if (!event) return null

    const remaining = state.events.filter((item) => Number(item?.id) !== normalizedEventId)
    state.events = sortEvents([...remaining, event])
    persistDashboardSnapshot()
    return event
}

export async function saveCurrentUserProfile(payload) {
    const userId = Number(state.user?.id)
    if (!state.token || !Number.isFinite(userId)) {
        throw new Error('No authenticated user is available.')
    }

    await updateUser(state.apiBaseUrl, state.token, userId, payload)
    await initializeDashboardSession(true)
    return state.user
}

export function markCurrentUserFaceRegistered() {
    patchStoredAuthMeta({
        faceReferenceEnrolled: true,
    })

    state.faceStatus = {
        ...(state.faceStatus || {}),
        face_reference_enrolled: true,
    }

    if (state.user?.student_profile) {
        state.user = {
            ...state.user,
            student_profile: {
                ...state.user.student_profile,
                is_face_registered: true,
                registration_complete: true,
            },
        }
    }

    persistDashboardSnapshot()
    return state.user
}

export function applySchoolSettingsSnapshot(nextSchoolSettings) {
    state.schoolSettings = nextSchoolSettings ? { ...nextSchoolSettings } : null
    applyActiveTheme()
    persistDashboardSnapshot()
    return state.schoolSettings
}

export function clearDashboardSession() {
    localStorage.removeItem('aura_token')
    localStorage.removeItem('aura_user_roles')
    clearStoredAuthMeta()
    clearDashboardSnapshot()
    setToken('')
    resetDashboardState()
}

export function sessionUsesLimitedMode() {
    return Boolean(state.limitedMode)
}

export function getDashboardEventById(eventId) {
    const normalizedEventId = Number(eventId)
    if (!Number.isFinite(normalizedEventId)) return null
    return state.events.find((event) => Number(event?.id) === normalizedEventId) ?? null
}

export function hasAttendanceForEvent(eventId) {
    const normalizedEventId = Number(eventId)
    if (!Number.isFinite(normalizedEventId)) return false

    return state.attendanceRecords.some((attendance) => {
        return Number(attendance?.event_id) === normalizedEventId
            && isResolvedAttendanceRecord(attendance)
    })
}

export function getLatestAttendanceForEvent(eventId) {
    const normalizedEventId = Number(eventId)
    if (!Number.isFinite(normalizedEventId)) return null

    return state.attendanceRecords
        .filter((attendance) => Number(attendance?.event_id) === normalizedEventId)
        .sort((left, right) => {
            const leftTime = new Date(left?.time_in || left?.created_at || 0).getTime()
            const rightTime = new Date(right?.time_in || right?.created_at || 0).getTime()
            return rightTime - leftTime
        })[0] ?? null
}

export function hasOpenAttendanceForEvent(eventId) {
    const normalizedEventId = Number(eventId)
    if (!Number.isFinite(normalizedEventId)) return false

    return state.attendanceRecords.some((attendance) => {
        return Number(attendance?.event_id) === normalizedEventId
            && isOpenAttendanceRecord(attendance)
    })
}

export function sessionNeedsFaceRegistration() {
    const roleNames = getRoleNames(state.user)
    const isStudentSession = Boolean(state.user?.student_profile) || roleNames.includes('student')
    if (!isStudentSession) return false

    return !resolveStudentFaceRegistered(state.user, getStoredAuthMeta(), state.faceStatus)
}

export function getSessionRoleNames(user = state.user) {
    return getRoleNames(user)
}

export function sessionHasRole(roleName, user = state.user) {
    return hasRole(user, roleName)
}

export function isPrivilegedSession(user = state.user) {
    return isPrivilegedFaceUser(user)
}

export function isSchoolItSession(user = state.user) {
    return isSchoolItUser(user)
}

export function isAdminSession(user = state.user) {
    return isAdminUser(user)
}

export function getDefaultAuthenticatedRoute(user = state.user) {
    return isSchoolItSession(user)
        ? { name: 'SchoolItHome' }
        : isAdminSession(user)
        ? { name: 'AdminHome' }
        : isPrivilegedSession(user)
        ? { name: 'PrivilegedDashboard' }
        : { name: 'Home' }
}

export function useDashboardSession() {
    return {
        dashboardState: readonly(state),
        apiBaseUrl: computed(() => state.apiBaseUrl),
        token: computed(() => state.token),
        currentUser: computed(() => state.user),
        schoolSettings: computed(() => state.schoolSettings),
        events: computed(() => state.events),
        attendanceRecords: computed(() => state.attendanceRecords),
        faceStatus: computed(() => state.faceStatus),
        limitedMode: computed(() => state.limitedMode),
        needsFaceRegistration: computed(() => sessionNeedsFaceRegistration()),
        unreadAnnouncements: computed(() => 0),
        initializeDashboardSession,
        refreshAttendanceRecords,
        replaceAttendanceRecordsForEvent,
        upsertAttendanceRecordSnapshot,
        refreshSchoolSettings,
        refreshFaceStatus,
        ensureDashboardEvent,
        saveCurrentUserProfile,
        markCurrentUserFaceRegistered,
        applySchoolSettingsSnapshot,
        clearDashboardSession,
        sessionUsesLimitedMode,
        getDashboardEventById,
        hasAttendanceForEvent,
        getLatestAttendanceForEvent,
        hasOpenAttendanceForEvent,
        getSessionRoleNames,
        sessionHasRole,
        isPrivilegedSession,
        isSchoolItSession,
        isAdminSession,
        getDefaultAuthenticatedRoute,
        sessionNeedsFaceRegistration,
    }
}
